"""Created on 2026-08-09.

the values that decide a hop set

@author: wf
"""

from typing import Optional

from basemkit.yamlable import lod_storable


@lod_storable
class HopConfig:
    """Every value that can change which hops are found - see issue #4.

    A hop set is only evidence if the values that decided it are known, so
    the configuration is stored beside the hop set and a run is repeatable
    from it. The detector is named; the names are the offer of
    HopDetector.get_detectors.
    """

    detector: str = "Adaptive"
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
