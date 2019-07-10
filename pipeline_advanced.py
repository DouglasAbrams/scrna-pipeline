import argparse
import glob
import os
import yaml
import sys

import pypeliner.workflow
import pypeliner.app
import pypeliner.managed

from utils.config import Configuration

from workflows.run_cellranger import RunCellranger
from workflows.run_qc import RunQC
from workflows.run_cellassign import RunCellAssign
from workflows.run_collection import RunCollection

config = Configuration()

def create_workflow():
    print("Creating workflow.")
    workflow = pypeliner.workflow.Workflow()
    
    prefix = config.prefix
    workflow = RunCellranger(prefix,workflow,full=False)
    workflow = RunQC(prefix, workflow)
    workflow = RunCellAssign(prefix, workflow)
    workflow = RunCollection(workflow)

    return workflow

if __name__ == '__main__':

    argparser = argparse.ArgumentParser()
    pypeliner.app.add_arguments(argparser)

    parsed_args = argparser.parse_args()

    args = vars(parsed_args)
    workflow = create_workflow()
    pyp = pypeliner.app.Pypeline(config=args)
    pyp.run(workflow)
