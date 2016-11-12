# -*- coding: utf-8 -*-
import os
import psutil
from math import fsum
from raspysystem.raspytask import RasPyTask, RasPySimpleTask
from raspysystem.raspysamplelogger import RasPySampleLogger

class OSInfoTask(RasPySimpleTask):

    def __init__(self, parent, windows):
        RasPySimpleTask.__init__(self, parent, "system")

        self._usagelog = RasPySampleLogger(
            self.kernel().get_updates24h(),
            windows
        )

        # system
        self._unixkernel = None
        self._distro = None
        self._uptime = 0
        self._idletime = 0
        self._loadavg = list()
        self._cpus = list()

        self._hardware = None
        self._revision = None
        self._board = None

        # data from http://www.raspberrypi-spy.co.uk/2012/09/checking-your-raspberry-pi-board-version/
        self._raspirevs = dict()
        self._raspirevs["0002"] = "Model B Rev 1"
        self._raspirevs["0003"] = "Model B Rev 1"
        self._raspirevs["0004"] = "Model B Rev 2"
        self._raspirevs["0005"] = "Model B Rev 2"
        self._raspirevs["0006"] = "Model B Rev 2"
        self._raspirevs["0007"] = "Model A"      
        self._raspirevs["0008"] = "Model A"      
        self._raspirevs["0009"] = "Model A"     
        self._raspirevs["000d"] = "Model B Rev 2"
        self._raspirevs["000e"] = "Model B Rev 2"
        self._raspirevs["000f"] = "Model B Rev 2"
        self._raspirevs["0010"] = "Model B+"     
        self._raspirevs["0013"] = "Model B+"    
        self._raspirevs["0011"] = "Compute Module"
        self._raspirevs["0012"] = "Model A+"    
        self._raspirevs["0014"] = "Compute 512MB"
        self._raspirevs["0015"] = "Model A+"    
        self._raspirevs["a01041"] = "Pi 2 Model B"  
        self._raspirevs["a21041"] = "Pi 2 Model B"
        self._raspirevs["900092"] = "PiZero"
        self._raspirevs["a02082"] = "Pi 3 Model B" 
        self._raspirevs["a22082"] = "Pi 3 Model B"

    def _get_cpu_freq(self, maxcpu):
        freqs = list()
        for cpuid in range(maxcpu):
            path = "{}cpu{}/cpufreq/{}".format(
                "/sys/devices/system/cpu/",
                cpuid,
                "scaling_cur_freq"
            )
            with open(path, "r") as f:
                # freq is in kHz -> store Hertz
                f = int(f.readline().rstrip()) * 1000
                freqs.append(f)
        return freqs


    # this will only work for RasPi 1&2
    # expect processor followed by model name in /proc/procinfo
    def _get_cpu_infos(self):
        model_line = "model name\t: "
        hw_line = "Hardware\t: "
        rev_line = "Revision\t: "
        info_result = dict(
            models=list(),
            hardware="",
            revision="",
            board=""
        )

        with open("/proc/cpuinfo", "r") as f:            
            for line in f:
                result = None
                if line.find(model_line) >= 0:
                    result = line[len(model_line):].rstrip()
                    info_result["models"].append(result)

                elif line.find(hw_line) >= 0:
                    result = line[len(hw_line):].rstrip()
                    info_result["hardware"] = result

                elif line.find(rev_line) >= 0:
                    result = line[len(rev_line):].rstrip()
                    info_result["revision"] = result

        if info_result["revision"] in self._raspirevs:
            info_result["board"] = self._raspirevs[info_result["revision"]]
                
        return info_result

    def _update_cpus(self):
        num_cpu = psutil.cpu_count()
        freqs = self._get_cpu_freq(num_cpu)
        cpu_infos = self._get_cpu_infos()
        for i in range(num_cpu):
            self._cpus.append(dict(
                name="cpu{}".format(i),
                freq=freqs[i],
                model=cpu_infos["models"][i],
                usage=0
            ))
        
        self._hardware = cpu_infos["hardware"]
        self._revision = cpu_infos["revision"]
        self._board = cpu_infos["board"]

    def _update_unixkernel(self):
        with open("/proc/sys/kernel/osrelease", "r") as f:
            self._unixkernel = f.readline().rstrip()


    def _update_distro(self):
        target = "PRETTY_NAME="
        with open("/etc/os-release", "r") as f:
            for line in f:
                if line.find(target) >= 0:
                    # cut from target
                    # dont include newline and quote marks
                    self._distro = line[len(target)+1:-2]
                    break

    def _update_uptime(self):
        with open("/proc/uptime", "r") as f:
            buf = f.readline()
            buf = buf.split()
            self._uptime = float(buf[0])
            self._idletime = float(buf[1])

    def _update_cpu_usage(self):
        time = self.time()
        usages = psutil.cpu_percent(None, True)
        for i in range(len(self._cpus)):
            self._cpus[i]['usage'] = usages[i]

        total_usage = fsum(usages) / len(usages)
        self._usagelog.log(time.jstimestamp(), total_usage)

    def startup_event(self, db, cfg):
        self._update_unixkernel()
        self._update_distro()
        # +ISSUE
        # cpu info might not just be static data
        # freq could change on the fly...
        self._update_cpus()
        return True

    def run_event(self):
        self._loadavg = os.getloadavg()
        self._update_uptime()
        self._update_cpu_usage()
        return True

    def report_event(self):
        return dict(
            usage=self._usagelog.serialize(),
            kernel=self._unixkernel,
            distro=self._distro,
            uptime=self._uptime,
            idletime=self._idletime,
            loadavg=self._loadavg,
            cpus=self._cpus,
            hardware=self._hardware,
            revision=self._revision,
            board=self._board
        )
