"""工具箱路由：BCT/拼版/纸张/装柜/成本/材质库"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from .. import database as db
from ..engines.packtools import (BctInput, bct_calculate, container_load,
                                 cost_estimate, finish_db, imposition_calculate,
                                 ImpositionInput, material_db, paper_convert)

router = APIRouter(prefix="/api/tools", tags=["Tools"])


class BctReq(BaseModel):
    ect: float = 6800
    thickness: float = 3.0
    length: float
    width: float
    stackHeight: float = 2000
    safetyFactor: float = 1.6
    humidityDecay: float = 0.0


class ImpositionReq(BaseModel):
    boxWidth: float
    boxHeight: float
    sheetWidth: float = 889
    sheetHeight: float = 1194
    trim: float = 5.0
    glue: float = 0.0


class PaperReq(BaseModel):
    value: float
    paperType: str = "white-card"
    direction: str = "g2t"


class ContainerReq(BaseModel):
    containerId: str = "40HQ"
    boxLength: float
    boxWidth: float
    boxHeight: float
    boxWeightKg: float = 0.5


class CostReq(BaseModel):
    quantity: int = 1000
    areaM2: float
    grammage: float = 350
    paperPricePerKg: float = 7.5
    colors: int = 4
    printType: str = "offset"
    finishes: List[str] = []


@router.post("/bct")
def bct(req: BctReq):
    res = bct_calculate(BctInput(ect=req.ect, thickness=req.thickness,
                                 length=req.length, width=req.width,
                                 stack_height=req.stackHeight,
                                 safety_factor=req.safetyFactor,
                                 humidity_decay=req.humidityDecay))
    return res.__dict__


@router.post("/imposition")
def imposition(req: ImpositionReq):
    res = imposition_calculate(ImpositionInput(
        box_width=req.boxWidth, box_height=req.boxHeight,
        sheet_width=req.sheetWidth, sheet_height=req.sheetHeight,
        trim=req.trim, glue=req.glue))
    return {"best": res.best.__dict__, "alternatives":
            [a.__dict__ for a in res.alternatives],
            "maxCount": res.max_count, "utilization": res.utilization,
            "wasteArea": res.waste_area}


@router.post("/paper")
def paper(req: PaperReq):
    return paper_convert(req.value, req.paperType, req.direction)


@router.post("/container")
def container(req: ContainerReq):
    return container_load(req.containerId, req.boxLength, req.boxWidth,
                          req.boxHeight, req.boxWeightKg)


@router.post("/cost")
def cost(req: CostReq):
    return cost_estimate(req.quantity, req.areaM2, req.grammage,
                         req.paperPricePerKg, colors=req.colors,
                         print_type=req.printType, finishes=req.finishes)


@router.get("/materials")
def materials():
    return material_db()


@router.get("/finishes")
def finishes():
    return finish_db()
