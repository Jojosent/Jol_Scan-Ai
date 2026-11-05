"""Граничные значения и защита от недопустимого ответа AI."""
import math
import pytest
from app.ai.detector import DetectorError, classify_severity, parse_result
from app.config import Config


@pytest.mark.parametrize('area,confidence,expected',[(0,.9,'NONE'),(.1,.39,'NONE'),(.001,.8,'LOW'),(.025,.8,'MEDIUM'),(.08,.65,'HIGH'),(.08,.64,'MEDIUM'),(.02499,.9,'LOW'),(.07999,.9,'MEDIUM'),(.9,.4,'MEDIUM')])
def test_severity(area,confidence,expected):
    assert classify_severity(area,confidence)==expected


@pytest.mark.parametrize('area,confidence',[(-.1,.8),(1.1,.8),(.1,1.1),(math.nan,.5),(.3,math.inf)])
def test_invalid_inputs(area,confidence):
    with pytest.raises(ValueError):classify_severity(area,confidence)


def test_polygon_validation():
    config={k:getattr(Config,k) for k in ['HIGH_AREA_THRESHOLD','MEDIUM_AREA_THRESHOLD','MIN_CONFIDENCE']}
    with pytest.raises(DetectorError):
        parse_result({'defects':[{'confidence':.9,'label':'bad','box':[100,100,800,800],'polygon':[[0,0],[1200,0],[0,1200]]}]},config)
    assert parse_result({'summary':'Таза','defects':[]},config)['detections']==[]


def test_approximate_box_expands_to_valid_contour():
    config={k:getattr(Config,k) for k in ['HIGH_AREA_THRESHOLD','MEDIUM_AREA_THRESHOLD','MIN_CONFIDENCE']}
    result=parse_result({'defects':[{'confidence':.9,'label':'Шұңқыр','box':[210,210,690,690],
                                    'polygon':[[200,200],[700,200],[700,700],[200,700]]}]},config)
    assert result['detections'][0]['box']==[200,200,700,700]
