import subprocess
import os
import random
from interface.fastqdirectory import FastQDirectory
from interface.tenxanalysis import TenxAnalysis

from utils import config

class CellRanger(object):

    @staticmethod
    def cmd(command, args):
        cmd = ["cellranger", command]
        for flag, value in args.items():
            cmd.append("--{}".format(flag))
            cmd.append(value)
        cmd.append("--disable-ui")
        cmd.append("--nopreflight")
        return cmd

    @staticmethod
    def mkfastq(bcl_object):
        args = dict()
        args["id"] = bcl_object.id
        args["run"] = bcl_object.path
        args["csv"] = bcl_object.csv
        cmd = CellRanger.cmd("mkfastq",args)
        subprocess.call(cmd)
        return FastQDirectory(bcl_object.out())


    @staticmethod
    def count(fastq_object):
        args = dict()
        args["id"] = fastq_object.id
        args["fastqs"] = fastq_object.path
        args["sample"] = fastq_object.samples.sampleid[0]
        args["transcriptome"] = config.reference
        args["lanes"] = fastq_object.samples.lane[0]
        args["localmem"] = "46"
        args["localcores"] = "24"
        if not fastq_object.check_status():
            cmd = CellRanger.cmd("count",args)
            subprocess.call(cmd)
        return TenxAnalysis(fastq_object.results)

    @staticmethod
    def reanalyze(tenx_object):
        args = dict()
        args["id"] = tenx_object.id
        args["matrix"] = tenx_object.matrix
        args["params"] = tenx_object.params
        cmd = CellRanger.cmd("reanalyze", args)
        subprocess.call(cmd)


    def aggr(self):
        pass
