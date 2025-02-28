import pypeliner.workflow
import pypeliner.app
import pypeliner.managed

import sys
import os
import json
import shutil
import subprocess

from interface.tenxanalysis import TenxAnalysis
from utils.cloud import RdataStorage
from interface.qualitycontrol import QualityControl
from utils.cloud import SampleCollection
from interface.qualitycontrol import QualityControl
from interface.genemarkermatrix import GeneMarkerMatrix
from utils.plotting import celltypes, tsne_by_cell_type, umap_by_cell_type
from software.cellassign import CellAssign

from utils.config import Configuration, write_config

config = Configuration()

def RunDownload(sampleids, finished):
    rdatafac = RdataStorage()
    for i, sample in enumerate(sampleids):
        path = rdatafac.get_sce(sample)
        path_json = {sample: path}
        open(finished(i),"w").write(json.dumps(path_json))

def RunStatistics(workflow):
    all_samples = open(config.samples, "r").read().splitlines()
    workflow.transform (
        name = "pull_rdata",
        func = RunDownload,
        args = (
            all_samples,
            pypeliner.managed.TempOutputFile("sample_path.json","sample")
        )
    )
    return workflow
