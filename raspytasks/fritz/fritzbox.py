# -*- coding: utf-8 -*-
import requests
from requests.auth import HTTPDigestAuth
# import xml.etree.ElementTree as ET
import xml.etree.cElementTree as ET

class FritzboxReaderError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class FritzboxReader(object):

    def __init__(self, user, pw, timeout, ip):
        self._config = None
        self._timeout = timeout

        self._user = user
        self._pw = pw

        url = "http://{}:49000".format(ip)

        self._config = dict(
            # tr64 specs
            # https://www.broadband-forum.org/technical/download/TR-064.pdf
            Hosts=dict(
                url="{}/upnp/control/hosts".format(url),
                type="urn:dslforum-org:service:Hosts:1"
            ),
            WANDSLInterfaceConfig=dict(
                url="{}/upnp/control/wandslifconfig1".format(url),
                type="urn:dslforum-org:service:WANDSLInterfaceConfig:1"
            ),
            UserInterface=dict(
                url="{}/upnp/control/userif".format(url),
                type="urn:dslforum-org:service:UserInterface:1"
            ),
            DeviceInfo=dict(
                url="{}/upnp/control/deviceinfo".format(url),
                type="urn:dslforum-org:service:DeviceInfo:1"
            ),
            Time=dict(
                url="{}/upnp/control/time".format(url),
                type="urn:dslforum-org:service:Time:1"
            ),

            # upnp specs
            WANIPConnection=dict(
                # http://upnp.org/specs/gw/UPnP-gw-WANIPConnection-v1-Service.pdf
                url="{}/igdupnp/control/WANIPConn1".format(url),
                type="urn:schemas-upnp-org:service:WANIPConnection:1"
            ),
            WANCommonInterfaceConfig=dict(
                # http://upnp.org/specs/gw/UPnP-gw-WANCommonInterfaceConfig-v1-Service.pdf
                url="{}/upnp/control/wancommonifconfig1".format(url),
                # somehow this uses another service id????
                # see http://www.fhemwiki.de/wiki/FRITZBOX
                #type="urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1"
                type="urn:dslforum-org:service:WANCommonInterfaceConfig:1"
            )
        )

    def _exec_soapcall(self, service, action, params=str()):
        # create request
        req = "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
        req += "<s:Envelope "
        req += "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\" "
        req += "xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\">"
        req += "<s:Body>"
        req += "<u:{} xmlns:u=\"{}\">{}</u:{}>".format(
            action,
            service["type"],
            params,
            action
        )
        req += "</s:Body>"
        req += "</s:Envelope>"


        # send request
        headers = dict()
        headers["Content-Type"] = "text/xml; charset=\"utf-8\""
        headers["Accept"] = "text/xml"
        headers["Cache-Control"] = "no-cache"
        headers["Pragma"] = "no-cache"
        headers["SoapAction"] = "{}#{}".format(service["type"], action)
        headers["Content-length"] = "{}".format(req)

        try:
            result = requests.post(
                service["url"],
                data=req,
                headers=headers,
                timeout=self._timeout,
                verify=False, # dont verify SSL certificate
                auth=HTTPDigestAuth(self._user, self._pw)
            )
        except requests.exceptions.Timeout:
            raise FritzboxReaderError("Timeout occured")
        except requests.exceptions.ConnectionError as e:
            raise FritzboxReaderError("Connection error: {}".format(e))

        if result.status_code != 200:
            raise FritzboxReaderError("Status is not OK: {}".format(result.status_code))

        # parse request
        root = ET.fromstring(result.content)
        search_string = ".//{{{}}}{}Response".format(service["type"], action)
        response = root.find(search_string)
        if response is None:
            return None
        items = dict()
        for child in response:
            items[child.tag] = child.text

        return items

    def hosts_get_specific_host_entry(self, newmac):
        return self._exec_soapcall(
            self._config["Hosts"],
            "GetSpecificHostEntry",
            "<NewMACAddress>{}</NewMACAddress>".format(newmac)
        )

    def wanip_get_status_info(self):
        return self._exec_soapcall(
            self._config["WANIPConnection"],
            "GetStatusInfo"
        )

    def wanif_get_total_bytes_sent(self):
        return self._exec_soapcall(
            self._config["WANCommonInterfaceConfig"],
            "GetTotalBytesSent"
        )

    def wanif_get_total_bytes_received(self):
        return self._exec_soapcall(
            self._config["WANCommonInterfaceConfig"],
            "GetTotalBytesReceived"
        )


    def devinfo_get_info(self):
        return self._exec_soapcall(
            self._config["DeviceInfo"],
            "GetInfo"
        )

    def userif_get_info(self):
        return self._exec_soapcall(
            self._config["UserInterface"],
            "GetInfo"
        )

    def wandslif_get_info(self):
        return self._exec_soapcall(
            self._config["WANDSLInterfaceConfig"],
            "GetInfo"
        )

    def time_get_info(self):
        return self._exec_soapcall(
            self._config["Time"],
            "GetInfo"
        )
