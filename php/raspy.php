<?php

class RasPy  {
	const RASPY_ADDRESS = 'localhost';
	const RASPY_PORT = 1337;
	const RESPONSE_LENGTH = 256;

    const STATUS_LEN = 3;
    // from pikernel.py
    const ERR_NONE = 'E00';
    const ERR_NOTRUNYET = 'E01';
    const ERR_NOTUPDATED = 'E02';
    const ERR_REQUEST_FAILED = 'E03';
    const ERR_INVALID_QUERY = 'E04';
    // added and leave buffer in case kernel adds errors
    const ERR_NOT_AUTHORIZED = 'E21';
    const ERR_INVALID_TASK = 'E22';
    const ERR_MISSING_TASK = 'E23';
    const ERR_NOT_RUNNING = 'E24';
    const ERR_SOCKET = 'E25';
    const ERR_MISSING_CMD = 'E26';
    const ERR_MISSING_ARG = 'E27';
    const ERR_INVALID_CMD = 'E28';
    const ERR_INVALID_ARG = 'E29';

    private $tasknames;
    private $config;

    private $taskname;
    private $timestamp;
    private $reduced;
    private $authorized;

	public function __construct($path, $taskname=NULL, $timestamp = 0, $reduced = false, $authorized = false) {

        $this->taskname = $taskname;
        $this->timestamp = $timestamp;
        $this->reduced = $reduced;
        $this->authorized = $authorized;
        $this->path = $path;

        $this->tasknames = array(
            'supply',
            'system',
            'weather',
            'fritz',
            'sensor',
            'notifier',
            'traffic',
            'rcsocket'
        );

		// read config
		$this->config = json_decode(
            file_get_contents($path . 'config.json'),
            true
        );
	}

    public function getPath() {
        return $this->path;
    }

	public function getApiKey() {
		return $this->config['apikey'];
	}

    public function getConfig() {
        return $this->config[$this->taskname];
    }

    public function validTask($taskname) {
        return in_array($taskname, $this->tasknames);
    }

	public function getTasknames() {
        return $this->tasks;
    }

    public function parse_params($params) {

        // taskname
        if( !isset($params['task']) || !$this->validTask($params['task']) ) {
            return false;
        } else {
            $this->taskname = $params['task'];
        }

        // timestamp
        if( isset($params['timestamp']) ) {
            if( !is_numeric($params['timestamp']) ) {
                return false;
            }
            $this->timestamp = intval($params['timestamp']);
        }

        if( isset($params['reduced']) ) {
            if( $params['reduced'] === 'true' ) {
                $this->reduced = true;
            } else if( $params['reduced'] === 'false' ) {
                $this->reduced = false;
            } else {
                return false;
            }
        }

        if( isset($params['apikey']) ) {
            if( $params['apikey'] === $this->getApiKey() ) {
                $this->authorized = true;
            } else {
                return false;
            }
        }

        return true;
    }

	private function send_request($request, &$response) {
		$so = @socket_create(AF_INET, SOCK_STREAM, SOL_TCP);

		if($so === false) {
				$response = $this::ERR_SOCKET;
                return false;
		} else {
			if (@socket_connect($so, $this::RASPY_ADDRESS, $this::RASPY_PORT) === false) {
                $response = $this::ERR_NOT_RUNNING;
				return false;
			} else {
				socket_write($so, $request, strlen($request));

				$response = '';
				while(true) {
					$buf = socket_read($so, $this::RESPONSE_LENGTH);
					if( strlen($buf) == 0 )
						break;
					$response .= $buf;
				}
				socket_close($so);

                // strip kernel status
                $status = substr($response, 0, $this::STATUS_LEN);
                if( $status == $this::ERR_NONE ) {
                    $response = substr($response, $this::STATUS_LEN);
                    return true;
                }
                return false;
			}
		}
	}

    private function reduce_samplelogger(&$logger) {
        unset($logger['samples']);
        unset($logger['avgsamples']);
    }

    private function reduce_energymeter(&$energy) {
        $this->reduce_samplelogger($energy['logs']['day']);
        $this->reduce_samplelogger($energy['logs']['week']);
        $this->reduce_samplelogger($energy['logs']['month']);
    }

    private function obfuscate($string) {
        // return 8 char string
        $len = strlen($string);
        if($len > 2) {
            $string = $string[0] . str_repeat('*', /*$len-2*/8);
        }
        return $string;
    }

    // truncate, nomnomnom ;-)
    private function postprocess_payload($response) {

        // only parse json once, on either api or short!!!
        if($this->authorized && !$this->reduced) {
            return $response;
        }

        $response = json_decode($response, true);
        $info = &$response['info'];
        $report = &$response['report'];

        // reduce first
        // then remove api

        if($this->reduced) {
            // $this->reduce_samplelogger($info['totaltime']);
            unset($info['totaltime']);

            switch($this->taskname) {
                case 'supply':
                    $this->reduce_samplelogger($report['voltage']);
                    $this->reduce_samplelogger($report['current']);
                    $this->reduce_samplelogger($report['power']);
                    // remove energymeter completely
                    unset($report['energy']);
                    break;
                case 'system':
                    $this->reduce_samplelogger($report['net']['rx']['rates']);
                    $this->reduce_samplelogger($report['net']['tx']['rates']);

                    $this->reduce_samplelogger($report['disk']['write']['rate']['rates']);
                    $this->reduce_samplelogger($report['disk']['read']['rate']['rates']);

                    $this->reduce_samplelogger($report['system']['usage']);
                    $this->reduce_samplelogger($report['tempctrl']['speed']);
                    $this->reduce_samplelogger($report['tempctrl']['temp']);
                    break;
                case 'weather':
                    unset($report['forecast']['logs']);
                    unset($report['forecast']['hourly']);
                    unset($report['forecast']['daily']);
                    /*$this->reduce_samplelogger($report['forecast']['logs']['preci']);
                    $this->reduce_samplelogger($report['forecast']['logs']['clouds']);
                    $this->reduce_samplelogger($report['forecast']['logs']['temp']);*/
                    break;
                case 'sensor':
                    // remove log
                   /* foreach($report['sensors'] as &$sensor) {
                        unset($sensor['log']);
                    }*/
                    break;
                case 'fritz':
                    $this->reduce_samplelogger($report['dsl']['rx']['rate']['rates']);
                    $this->reduce_samplelogger($report['dsl']['tx']['rate']['rates']);
                    // remove log
                    foreach($report['devices'] as &$device) {
                        print_r($device['log']);
                        //unset($report['devices'][$key]['log']);
                    }
                    break;
                case 'rcsocket':
                    // remove log and energy
                    foreach($report['socketctrl']['sockets'] as &$socket) {
                        unset($socket['log']);
                        unset($socket['energy']);
                    }
                    break;
            }
        }

        if( !$this->authorized ) {
            unset($response->request);

            switch($this->taskname) {
                case 'supply':
                    break;
                case 'system':
                    break;
                case 'weather':
                    break;
                case 'sensor':
                    break;
                case 'traffic':
                    // only keep first
                    for($i=1;$i<count($report['directions']);++$i) {
                        unset($report['directions'][$i]);
                    }
                    break;
                case 'fritz':
                    // remove smartphones
                    unset($report['devices']);
                    break;
                case 'rcsocket':
                    foreach($report['socketctrl']['sockets'] as &$socket) {
                        // remove automat data
                        unset($socket['location']);
                        unset($socket['name']);
                        unset($socket['automat']);
                        unset($socket['automat_msg']);
                        unset($socket['log']);
                        unset($socket['energy']['logs']);
                    }
                    break;
            }
        }
        return json_encode($response);
    }

    private function response_wrap($success, $response) {
        $json = '{';
        $json .= '"success":' . ($success?'true':'false');
        if($success) {
            $json .= ',"payload":'. $response;
        } else {
            $json .= ',"payload":"'. $response . '"';
        }
        $json .= '}';
        return $json;
    }

    private function valid_command($command) {
        return preg_match(
            '/^[a-zA-Z0-9][_a-zA-Z0-9]*[a-zA-Z0-9]$/',
            $command
        ) === 1;
    }

	public function set_request($params) {

        if(!$this->authorized) {
            return $this->response_wrap(false, $this::ERR_NOT_AUTHORIZED);
        }

        if(!isset($params['command'])) {
            return $this->response_wrap(false, $this::ERR_MISSING_CMD);
        }

        // check format
        // valid: foo or foo.bar
        $command = $params['command'];
        $tree = explode('.', $command);
        $tree_len = count($tree);
        if(
            ($tree_len == 1 && !$this->valid_command($tree[0])) ||
            ($tree_len == 2 && !($this->valid_command($tree[0]) && $this->valid_command($tree[1])))
        ) {
            return $this->response_wrap(false, $this::ERR_INVALID_CMD);
        }

        if(!isset($params['payload'])) {
            return $this->response_wrap(false, $this::ERR_MISSING_ARG);
        }
        $payload = $params['payload'];

        // check if valid json
        json_decode($payload);
        if( json_last_error() != 0 ) {
            return $this->response_wrap(false, $this::ERR_INVALID_ARG);
        }

        // normal quotes to hex quotes
        $payload = htmlspecialchars($payload);

        $request = '{';
        $request .= '"type":"REQUEST"';
        $request .= ',"task":"' . $this->taskname . '"';
        $request .= ',"timestamp":0';
        $request .= ',"command":"' . $command . '"';
        $request .= ',"payload":"' . $payload . '"';
        $request .= '}';

        $response = '';
        $success = $this->send_request($request, $response);
        if( $success ) {
            $response = $this->postprocess_payload($response);
        }
        return $this->response_wrap($success, $response);
	}

	public function get_report() {
		$request = '{';
            $request .= '"type":"REPORT"';
            $request .= ',"task":"' . $this->taskname . '"';
            $request .= ',"timestamp":' . $this->timestamp;
        $request .= '}';

        $response = '';
        $success = $this->send_request($request, $response);
        if( $success ) {
            $response = $this->postprocess_payload($response);
        }
        return $this->response_wrap($success, $response);
	}

    public function quit() {

        if(!$this->authorized) {
            return $this->response_wrap(false, $this::ERR_NOT_AUTHORIZED);
        }

        $request = '{';
            $request .= '"type":"EXIT"';
        $request .= '}';
        return $this->response_wrap(
            true,
            $this->send_request($request)
        );
    }
}
