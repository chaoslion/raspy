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
    def _get_cpu_models(self, maxcpu):
        model_line = "model name\t: "
        model_line_len = len(model_line)
        models = list()

        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.find(model_line) >= 0:
                    model = line[model_line_len:].rstrip()
                    models.append(model)
        return models

    def _update_cpus(self):
        num_cpu = psutil.cpu_count()
        freqs = self._get_cpu_freq(num_cpu)
        models = self._get_cpu_models(num_cpu)
        for i in range(num_cpu):
            self._cpus.append(dict(
                name="cpu{}".format(i),
                freq=freqs[i],
                model=models[i],
                usage=0
            ))

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
        )
