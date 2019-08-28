import pypeliner.workflow
import pypeliner.app
import pypeliner.managed

import sys
import os
import json
import shutil
import subprocess

from interface.tenxanalysis import TenxAnalysis
from interface.singlecellexperiment import SingleCellExperiment
from utils.cloud import TenxDataStorage
from interface.qualitycontrol import QualityControl
from utils.cloud import SampleCollection
from interface.qualitycontrol import QualityControl
from interface.genemarkermatrix import GeneMarkerMatrix
from utils.plotting import celltypes, tsne_by_cell_type, umap_by_cell_type
from software.cellassign import CellAssign

from utils.config import Configuration, write_config

config = Configuration()

def RunDownload(sampleids, finished):
    for i, sample in enumerate(sampleids):
        tenx = TenxDataStorage(sample)
        path = tenx.download()
        path_json = {sample: path}
        open(finished(i),"w").write(json.dumps(path_json))

def RunExtract(sample_to_path, rdata_path, summary_path, metrics_path):
    sample = json.loads(open(sample_to_path,"r").read())
    sampleid, path = list(sample.items()).pop()
    tenx_analysis = TenxAnalysis(path)
    tenx_analysis.load()
    tenx_analysis.extract()
    qc = QualityControl(tenx_analysis, sampleid)
    if not os.path.exists(qc.sce):
        qc.run(mito=config.mito)
    shutil.copyfile(tenx_analysis.summary, summary_path)
    shutil.copyfile(tenx_analysis.metrics_summary, metrics_path)
    shutil.copyfile(qc.sce, rdata_path)

def RunCellAssign(sce, annot_sce, cellfit):
    _rho_csv = os.path.join(os.path.split(sce)[0],"rho_csv_sub.csv")
    _fit = os.path.join(os.path.split(sce)[0],"fit_sub.pkl")
    sampleid = sce.split("/")[-2]
    filtered_sce = os.path.join(os.path.split(sce)[0],"sce_cas.rdata")
    if not os.path.exists(filtered_sce) or not os.path.exists(_fit):
        CellAssign.run(sce, config.rho_matrix, _fit, rho_csv=_rho_csv)
    shutil.copyfile(filtered_sce, annot_sce)
    shutil.copyfile(_fit,cellfit)

def RunConvert(sce, seurat):
    seurat_cached = os.path.join(os.path.split(sce)[0],"seurat_raw.rdata")
    sce_cached = os.path.join(os.path.split(sce)[0],"sce_cas.rdata")
    rcode = """
    library(Seurat)
    library(SingleCellExperiment)
    library(scater)
    sce <- readRDS('{sce}')
    rownames(sce) <- uniquifyFeatureNames(rowData(sce)$ensembl_gene_id, rownames(sce))
    seurat <- as.Seurat(sce, counts = "counts", data = "logcounts")
    saveRDS(seurat,file='{seurat}')
    """
    path = os.path.split(sce)[0]
    convert_script = os.path.join(path,"convert.R")
    output = open(convert_script,"w")
    output.write(rcode.format(sce=sce_cached,seurat=seurat_cached))
    output.close()
    if not os.path.exists(seurat_cached):
        subprocess.call(["Rscript","{}".format(convert_script)])
    shutil.copyfile(seurat_cached, seurat)

def RunSeuratWorkflow(seurat, qcd_seurat, qcd_sce):
    seurat_cached = os.path.join(os.path.split(seurat)[0],"seuret_annot.rdata")
    sce_cached = os.path.join(os.path.split(seurat)[0],"sce_annot.rdata")
    rcode = """
    library(Seurat)
    library(sctransform)
    seurat <- readRDS("{seurat}")
    seurat <- SCTransform(object = seurat)
    seurat <- RunPCA(object = seurat)
    seurat <- FindNeighbors(object = seurat)
    seurat <- FindClusters(object = seurat)
    seurat <- RunTSNE(object = seurat)
    seurat <- RunUMAP(object = seurat, reduction = "pca", dims = 1:20)
    saveRDS(seurat, file = '{qcd_seurat}')
    sce <- as.SingleCellExperiment(seurat)
    saveRDS(sce, file="{qcd_sce}")
    """
    path = os.path.split(seurat)[0]
    qc_script = os.path.join(path,"qc.R")
    output = open(qc_script,"w")
    output.write(rcode.format(seurat=seurat, qcd_seurat=seurat_cached, qcd_sce=sce_cached))
    output.close()
    if not os.path.exists(seurat_cached) or not os.path.exists(sce_cached):
        subprocess.call(["Rscript", "{}".format(qc_script)])
    shutil.copyfile(seurat_cached, qcd_seurat)
    shutil.copyfile(sce_cached, qcd_sce)

def RunSeuratViz(seurat, tsne, umap, tsne_celltype, umap_celltype, ridge, exprs):
    marker_list = GeneMarkerMatrix.read_yaml(config.rho_matrix)
    markers = ["'" + marker + "'" for marker in marker_list.genes]
    tsne_plot = os.path.join(os.path.split(seurat)[0],"tsne.png")
    umap_plot = os.path.join(os.path.split(seurat)[0],"umap.png")
    tsne_celltype_plot = os.path.join(os.path.split(seurat)[0],"tsne_celltype.png")
    umap_celltype_plot = os.path.join(os.path.split(seurat)[0],"umap_celltype.png")
    ridge_plot = os.path.join(os.path.split(seurat)[0],"ridge.png")
    exprs_plot = os.path.join(os.path.split(seurat)[0],"features.png")
    rcode = """
    library(Seurat)
    library(ggplot2)
    seurat <- readRDS("{seurat}")

    png("{tsne}")
    DimPlot(object = seurat, reduction = "tsne")
    dev.off()
    png("{umap}")
    DimPlot(object = seurat, reduction = "umap")
    dev.off()

    png("{tsne_celltype}")
    DimPlot(object = seurat, reduction = "tsne", group.by = "cell_type")
    dev.off()
    png("{umap_celltype}")
    DimPlot(object = seurat, reduction = "umap", group.by = "cell_type")
    dev.off()

    png("{ridge}",width=600,heigh=5000)
    RidgePlot(object = seurat, features = c({markers}), ncol = 2)
    dev.off()

    png("{exprs}",width=600,heigh=5000)
    FeaturePlot(object = seurat, features = c({markers}), ncol= 2)
    dev.off()
    """
    path = os.path.split(seurat)[0]
    qc_script = os.path.join(path,"viz.R")
    output = open(qc_script,"w")
    output.write(rcode.format(seurat=seurat, tsne=tsne_plot, umap=umap_plot, tsne_celltype=tsne_celltype_plot, umap_celltype=umap_celltype_plot, markers=",".join(markers), ridge = ridge_plot, exprs=exprs_plot))
    output.close()
    if not os.path.exists(exprs_plot):
        subprocess.call(["Rscript","{}".format(qc_script)])
    shutil.copyfile(tsne_plot, tsne)
    shutil.copyfile(umap_plot, umap)
    shutil.copyfile(tsne_celltype_plot, tsne_celltype)
    shutil.copyfile(umap_celltype_plot, umap_celltype)
    shutil.copyfile(ridge_plot, ridge)
    shutil.copyfile(exprs_plot, exprs)

def RunMarkers(seurat,marker_table):
    marker_csv_cached = os.path.join(os.path.split(seurat)[0],"marker_table.csv")
    rcode = """
    library(Seurat)
    library(dplyr)
    seurat <- readRDS("{seurat}")
    markers <- FindAllMarkers(seurat, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)
    marker_table <- markers %>% group_by(cluster) %>% top_n(n = 20, wt = avg_logFC)
    marker_table <- as.data.frame(marker_table)
    write.csv(marker_table, file = "{marker_csv}")
    """
    path = os.path.split(seurat)[0]
    marker_script = os.path.join(path,"markers.R")
    output = open(marker_script,"w")
    output.write(rcode.format(seurat=seurat, marker_csv=marker_csv_cached))
    output.close()
    if not os.path.exists(marker_csv_cached):
        subprocess.call(["Rscript","{}".format(marker_script)])
    shutil.copyfile(marker_csv_cached, marker_table)

def RunIntegration(seurats, integrated_seurat, integrated_sce):
    rdata = os.path.join(os.path.split(integrated_seurat)[0],"integrate_seurat_cached.rdata")
    sce_cached = os.path.join(os.path.split(integrated_seurat)[0],"integrate_sce_cached.rdata")
    object_list = []
    rcode = """
    library(Seurat)
    """
    for idx, object in seurats.items():
        seurat_obj = "seurat{}".format(idx)
        object_list.append(seurat_obj)
        load = """
    seurat{id} <- readRDS("{object}")
        """.format(id=idx,object=object)
        rcode += load
    rcode += """
    object_list <- c({object_list})
    features <- SelectIntegrationFeatures(object.list = c({object_list}), nfeatures = 3000)
    prepped <- PrepSCTIntegration(object.list = c({object_list}), anchor.features = features)
    anchors <- FindIntegrationAnchors(object.list = prepped, normalization.method="SCT", anchor.features=features)
    integrated <- IntegrateData(anchorset = anchors, normalization="SCT")
    saveRDS(integrated, file = "{rdata}")
    integrated <- RunPCA(integrated, verbose = FALSE)
    integrated <- RunUMAP(integrated, dims = 1:30)
    saveRDS(integrated, file ="{rdata}")
    sce <- as.SingleCellExperiment(integrated)
    saveRDS(sce, file="{sce}")
    """
    integrate_script = os.path.join(".cache/integration.R")
    output = open(integrate_script,"w")
    output.write(rcode.format(seurat=seurat, object_list=",".join(object_list), rdata=rdata, sce=sce_cached))
    output.close()
    if not os.path.exists(sce_cached):
        subprocess.call(["Rscript","{}".format(integrate_script)])
    shutil.copyfile(rdata, integrated_seurat)
    shutil.copyfile(sce_cached, integrated_sce)

def dump_all_coldata(sce):
    counts = sce.colData
    column_data = dict()
    for key in counts.keys():
        if type(counts[key]) == list:
            if "endogenous" in key: continue
            if "top_50_features" in key or "top_100_features" in key or "top_200_features" in key or "top_500_features" in key: continue
            if "control" in key: continue
            column_data[key] = counts[key]
    return column_data

def dump_all_rowdata(sce):
    counts = sce.rowData
    column_data = dict()
    for key in counts.keys():
        if type(counts[key]) == list:
            if "is_" in key: continue
            if "NA" in str(key): continue
            if "entrezgene" in key: continue
            column_data[key] = counts[key]
    print (column_data.keys())
    return column_data

def find_chemistry(summary):
    rows = open(summary,"r").read().splitlines()
    for i, row in enumerate(rows):
        if "Chemistry" in row:
            break
    chem = rows[i+1].strip().replace("<td>","").replace("</td>","")
    return chem

def load_summary(metrics):
    rows = open(metrics,"r").read().splitlines()
    header = rows.pop(0)
    header = pp.commaSeparatedList.parseString(header).asList()
    stats = rows.pop(0)
    stats = pp.commaSeparatedList.parseString(stats).asList()
    assert len(header) == len(stats), "{} - {}".format(len(header),len(stats))
    for i,stat in enumerate(stats):
        stats[i] = stat.replace(",","").replace('"',"")
    return dict(zip(header,stats))

def load_mito(stats_file):
    perc_path = os.path.join(stats_file)
    results = open(perc_path,"r").read().splitlines()[2].split()[-1].strip()
    return results

def get_statistics(web_summary, metrics, patient_summary):
    cols = ["Sample","Chemistry","Mito5","Mito10","Mito15","Mito20"]
    sample_stats = {}
    final_stats = dict()
    summary = os.path.join(web_summary)
    metrics = os.path.join(metrics)
    chem = find_chemistry(summary)
    res = load_summary(metrics)
    mito20 = load_mito()
    cols += res.keys()
    res["Chemistry"] = chem
    res["Sample"] = name
    res["Mito5"] = mito5
    res["Mito10"] = mito10
    res["Mito15"] = mito15
    res["Mito20"] = mito20
    sample_stats[name] = res
    output = open(patient_summary,"w")
    output.write("\t".join(cols)+"\n")
    for sample in sample_stats:
        row = []
        columns = []
        for col in cols:
            if "Q30" in col: continue
            columns.append(col)
            row.append(sample_stats[sample][col])
        row = [x.replace('"','').replace(",","") for x in row]
        final_stats[sample] = dict(zip(columns, row))
        output.write("\t".join(row)+"\n")
    output.close()
    return final_stats

def RunSampleSummary(summary, sce, report, metrics, cellassign_fit):
    sce = SingleCellExperiment.fromRData(sce)
    column_data = dump_all_coldata(sce)
    patient_data = collections.defaultdict(dict)
    patient_data[sample]["celldata"] = column_data
    gene_data = dump_all_rowdata(sce)
    patient_data[sample]["genedata"] = gene_data
    counts = sce.assays["counts"].todense().tolist()
    logcounts = sce.assays["logcounts"].todense().tolist()
    count_matrix = collections.defaultdict(dict)
    log_count_matrix = collections.defaultdict(dict)
    for symbol, row in zip(gene_data["Symbol"],counts):
        for barcode, cell in zip(column_data["Barcode"],row):
            if float(cell) != 0.0:
                count_matrix[barcode][symbol] = cell
    for symbol, row in zip(gene_data["Symbol"],logcounts):
        for barcode, cell in zip(column_data["Barcode"],row):
            if float(cell) != 0.0:
                log_count_matrix[barcode][symbol] = cell
    patient_data[sample]["matrix"] = dict(count_matrix)
    patient_data[sample]["log_count_matrix"] = dict(log_count_matrix)
    patient_data[sample]["web_summary"] = summary
    rdims = sce.reducedDims["UMAP"]
    barcodes = sce.colData["Barcode"]
    rdims = numpy.array(rdims).reshape(2, len(barcodes))
    cellassign = pickle.load(cellassign_fit,"rb")
    celltypes = []
    for celltype in cellassign["cell_type"]:
        if celltype == "Monocyte.Macrophage":
            celltype = "Monocyte/Macrophage"
        else:
            celltype = celltype.replace("."," ")
        celltypes.append(celltype)
    fit = dict(zip(cellassign["Barcode"],celltypes))
    x_coded = dict(zip(barcodes, rdims[0]))
    y_coded = dict(zip(barcodes, rdims[1]))
    coords = dict()
    for barcode, celltype in fit.items():
        try:
            x_val = x_coded[barcode]
            y_val = y_coded[barcode]
        except Exception as e:
            continue
        coords[barcode] = (x_val, y_val)
    patient_data[sample]["cellassign"] = fit
    patient_data[sample]["umap"] = coords
    outputqc=open("runqc_{}.sh".format(sample),"w")
    rdata = "../../{0}/runs/.cache/{0}/{0}.rdata".format(sample)
    stats = ".cache/stats.tsv"
    qcscript = os.path.join(".cache/qcthresh.R")
    rcode = """
    library(SingleCellExperiment)
    rdata <- readRDS('{sce}')
    sce <- as(rdata, 'SingleCellExperiment')
    cells_to_keep <- sce$pct_counts_mito < as.numeric(20)
    table_cells_to_keep <- table(cells_to_keep)
    write.table(table_cells_to_keep, file='{stats}',sep="\t")
    """
    output.write(rcode.format(seurat=sce, stats=stats))
    output.close()
    subprocess.call(["Rscript",".cache/qcthresh.R"])
    patient_data["statistics"] = get_statistics(summary, metrics, report, stats)
    patient_data["rho"] = GeneMarkerMatrix.read_yaml(config.markers).marker_list
    patient_data_str = json.dumps(patient_data)
    output = open("../report/{}.json".format(given_sample),"w")
    output.write(str(patient_data_str))
    output.close()



def RunCollection(workflow):
    all_samples = open(config.samples, "r").read().splitlines()
    workflow.transform (
        name = "download_collection",
        func = RunDownload,
        args = (
            all_samples,
            pypeliner.managed.TempOutputFile("sample_path.json","sample")
        )
    )
    workflow.transform (
        name = "extract_rdata",
        func = RunExtract,
        axes = ('sample',),
        args = (
            pypeliner.managed.TempInputFile("sample_path.json","sample"),
            pypeliner.managed.TempOutputFile("sample.rdata","sample"),
            pypeliner.managed.TempOutputFile("summary.html","sample"),
            pypeliner.managed.TempOutputFile("metrics.csv","sample")
        )
    )

    workflow.transform (
        name = "run_cellassign",
        func = RunCellAssign,
        axes = ('sample',),
        args = (
            pypeliner.managed.TempInputFile("sample.rdata","sample"),
            pypeliner.managed.TempOutputFile("sce.rdata","sample"),
            pypeliner.managed.TempOutputFile("cellassign.pkl","sample")
        )
    )

    workflow.transform (
        name = "run_convert",
        func = RunConvert,
        axes = ('sample',),
        args = (
            pypeliner.managed.TempInputFile("sce.rdata","sample"),
            pypeliner.managed.TempOutputFile("seurat.rdata","sample"),
        )
    )

    workflow.transform (
        name = "run_qc",
        func = RunSeuratWorkflow,
        axes = ('sample',),
        args = (
            pypeliner.managed.TempInputFile("seurat.rdata","sample"),
            pypeliner.managed.TempOutputFile("seurat_qcd.rdata","sample"),
            pypeliner.managed.TempOutputFile("sce_qcd.rdata","sample"),
        )
    )

    workflow.transform (
        name = "visualize_sample",
        func = RunSeuratViz,
        axes = ('sample',),
        args = (
            pypeliner.managed.TempInputFile("seurat_qcd.rdata","sample"),
            pypeliner.managed.TempOutputFile("seurat_tsne.png","sample"),
            pypeliner.managed.TempOutputFile("seurat_umap.png","sample"),
            pypeliner.managed.TempOutputFile("seurat_tsne_celltype.png","sample"),
            pypeliner.managed.TempOutputFile("seurat_umap_celltype.png","sample"),
            pypeliner.managed.TempOutputFile("seurat_ridge.png","sample"),
            pypeliner.managed.TempOutputFile("seurat_features.png","sample"),
        )
    )

    workflow.transform (
        name = "find_markers",
        func = RunMarkers,
        axes = ('sample',),
        args = (
            pypeliner.managed.TempInputFile("seurat_qcd.rdata","sample"),
            pypeliner.managed.TempOutputFile("markers.csv","sample"),
        )
    )

    workflow.transform (
        name = "integrate",
        func = RunIntegration,
        args = (
            pypeliner.managed.TempInputFile("seurat_qcd.rdata","sample"),
            pypeliner.managed.TempOutputFile("seurat_integrated.rdata"),
            pypeliner.managed.TempOutputFile("sce_integrated.rdata"),
        )
    )

    workflow.transform (
        name = "sample_level",
        func = RunSampleSummary,
        axes = ('sample',),
        args = (
            pypeliner.managed.TempInputFile("summary.html","sample"),
            pypeliner.managed.TempInputFile("sce_qcd.rdata","sample"),
            pypeliner.managed.TempInputFile("cellassign.pkl","sample"),
            pypeliner.managed.TempInputFile("metrics.csv","sample"),
            pypeliner.managed.TempOutputFile("report.json","sample"),
        )
    )


    return workflow
