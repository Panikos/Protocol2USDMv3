"""
USDM Type Definitions - Typed dataclasses for USDM v4.0 entities.

These types provide:
- Type safety and IDE autocompletion
- Validation of required fields
- Easy serialization to/from JSON
- Documentation of USDM structure

Usage:
    from core.usdm_types import Activity, PlannedTimepoint, HeaderStructure
    
    activity = Activity(id="act_1", name="Vital Signs")
    data = activity.to_dict()
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum


class EntityType(Enum):
    """USDM entity instance types."""
    ACTIVITY = "Activity"
    PLANNED_TIMEPOINT = "PlannedTimepoint"
    ENCOUNTER = "Encounter"
    EPOCH = "Epoch"
    ACTIVITY_GROUP = "ActivityGroup"
    ACTIVITY_TIMEPOINT = "ActivityTimepoint"


@dataclass
class Code:
    """CDISC-style coded value."""
    code: str
    decode: str
    codeSystem: Optional[str] = None
    codeSystemVersion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Code':
        if not data:
            return None
        return cls(
            code=data.get('code', ''),
            decode=data.get('decode', ''),
            codeSystem=data.get('codeSystem'),
            codeSystemVersion=data.get('codeSystemVersion'),
        )


@dataclass
class Timing:
    """Encounter timing information."""
    windowLabel: Optional[str] = None
    windowLower: Optional[int] = None
    windowUpper: Optional[int] = None
    unit: Optional[str] = None
    anchorEvent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Activity:
    """USDM Activity entity - a procedure or assessment."""
    id: str
    name: str
    instanceType: str = "Activity"
    description: Optional[str] = None
    activityGroupId: Optional[str] = None
    biomedicalConceptId: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Activity':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            instanceType=data.get('instanceType', 'Activity'),
            description=data.get('description'),
            activityGroupId=data.get('activityGroupId'),
            biomedicalConceptId=data.get('biomedicalConceptId'),
        )


@dataclass
class PlannedTimepoint:
    """USDM PlannedTimepoint entity - a scheduled moment."""
    id: str
    name: str
    instanceType: str = "PlannedTimepoint"
    description: Optional[str] = None
    encounterId: Optional[str] = None
    value: Optional[int] = None
    valueLabel: Optional[str] = None
    windowLabel: Optional[str] = None
    windowLower: Optional[int] = None
    windowUpper: Optional[int] = None
    unit: Optional[str] = None
    type: Optional[Code] = None
    relativeToFrom: Optional[Code] = None
    relativeFromScheduledInstanceId: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if isinstance(v, dict):
                    result[k] = v
                else:
                    result[k] = v
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PlannedTimepoint':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            instanceType=data.get('instanceType', 'PlannedTimepoint'),
            description=data.get('description'),
            encounterId=data.get('encounterId'),
            value=data.get('value'),
            valueLabel=data.get('valueLabel'),
            windowLabel=data.get('windowLabel'),
            windowLower=data.get('windowLower'),
            windowUpper=data.get('windowUpper'),
            unit=data.get('unit'),
            type=Code.from_dict(data.get('type')) if data.get('type') else None,
            relativeToFrom=Code.from_dict(data.get('relativeToFrom')) if data.get('relativeToFrom') else None,
            relativeFromScheduledInstanceId=data.get('relativeFromScheduledInstanceId'),
        )


@dataclass
class Encounter:
    """USDM Encounter entity - a visit."""
    id: str
    name: str
    instanceType: str = "Encounter"
    description: Optional[str] = None
    epochId: Optional[str] = None
    type: Optional[Code] = None
    timing: Optional[Timing] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {'id': self.id, 'name': self.name, 'instanceType': self.instanceType}
        if self.description:
            result['description'] = self.description
        if self.epochId:
            result['epochId'] = self.epochId
        if self.type:
            result['type'] = self.type.to_dict() if isinstance(self.type, Code) else self.type
        if self.timing:
            result['timing'] = self.timing.to_dict() if isinstance(self.timing, Timing) else self.timing
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Encounter':
        timing_data = data.get('timing')
        timing = None
        if timing_data and isinstance(timing_data, dict):
            timing = Timing(**{k: v for k, v in timing_data.items() if k in Timing.__dataclass_fields__})
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            instanceType=data.get('instanceType', 'Encounter'),
            description=data.get('description'),
            epochId=data.get('epochId'),
            type=Code.from_dict(data.get('type')) if data.get('type') else None,
            timing=timing,
        )


@dataclass
class Epoch:
    """USDM Epoch entity - a study phase."""
    id: str
    name: str
    instanceType: str = "Epoch"
    description: Optional[str] = None
    position: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Epoch':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            instanceType=data.get('instanceType', 'Epoch'),
            description=data.get('description'),
            position=data.get('position'),
        )


@dataclass
class ActivityGroup:
    """USDM ActivityGroup entity - groups related activities."""
    id: str
    name: str
    instanceType: str = "ActivityGroup"
    description: Optional[str] = None
    activities: List[str] = field(default_factory=list)  # List of activity names or IDs
    
    def to_dict(self) -> Dict[str, Any]:
        result = {'id': self.id, 'name': self.name, 'instanceType': self.instanceType}
        if self.description:
            result['description'] = self.description
        if self.activities:
            result['activities'] = self.activities
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActivityGroup':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            instanceType=data.get('instanceType', 'ActivityGroup'),
            description=data.get('description'),
            activities=data.get('activities', []),
        )


@dataclass
class ActivityTimepoint:
    """USDM ActivityTimepoint - maps activity to timepoint (a tick)."""
    id: str
    activityId: str
    plannedTimepointId: str
    instanceType: str = "ActivityTimepoint"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActivityTimepoint':
        return cls(
            id=data.get('id', ''),
            activityId=data.get('activityId', ''),
            plannedTimepointId=data.get('plannedTimepointId') or data.get('timepointId', ''),
            instanceType=data.get('instanceType', 'ActivityTimepoint'),
        )


@dataclass
class HeaderStructure:
    """
    Structure extracted from SoA table headers by vision analysis.
    
    This is the OUTPUT of vision analysis and INPUT to text extraction.
    It provides the structural anchor that text extraction must follow.
    """
    epochs: List[Epoch] = field(default_factory=list)
    encounters: List[Encounter] = field(default_factory=list)
    plannedTimepoints: List[PlannedTimepoint] = field(default_factory=list)
    activityGroups: List[ActivityGroup] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'columnHierarchy': {
                'epochs': [e.to_dict() for e in self.epochs],
                'encounters': [e.to_dict() for e in self.encounters],
                'plannedTimepoints': [pt.to_dict() for pt in self.plannedTimepoints],
            },
            'rowGroups': [g.to_dict() for g in self.activityGroups],
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HeaderStructure':
        col_h = data.get('columnHierarchy', {})
        return cls(
            epochs=[Epoch.from_dict(e) for e in col_h.get('epochs', [])],
            encounters=[Encounter.from_dict(e) for e in col_h.get('encounters', [])],
            plannedTimepoints=[PlannedTimepoint.from_dict(pt) for pt in col_h.get('plannedTimepoints', [])],
            activityGroups=[ActivityGroup.from_dict(g) for g in data.get('rowGroups', [])],
        )
    
    def get_timepoint_ids(self) -> List[str]:
        """Get ordered list of timepoint IDs."""
        return [pt.id for pt in self.plannedTimepoints]
    
    def get_encounter_ids(self) -> List[str]:
        """Get ordered list of encounter IDs."""
        return [enc.id for enc in self.encounters]
    
    def get_group_ids(self) -> List[str]:
        """Get ordered list of activity group IDs."""
        return [g.id for g in self.activityGroups]


@dataclass
class Timeline:
    """USDM Timeline containing all SoA entities."""
    activities: List[Activity] = field(default_factory=list)
    plannedTimepoints: List[PlannedTimepoint] = field(default_factory=list)
    encounters: List[Encounter] = field(default_factory=list)
    epochs: List[Epoch] = field(default_factory=list)
    activityGroups: List[ActivityGroup] = field(default_factory=list)
    activityTimepoints: List[ActivityTimepoint] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'activities': [a.to_dict() for a in self.activities],
            'plannedTimepoints': [pt.to_dict() for pt in self.plannedTimepoints],
            'encounters': [e.to_dict() for e in self.encounters],
            'epochs': [e.to_dict() for e in self.epochs],
            'activityGroups': [g.to_dict() for g in self.activityGroups],
            'activityTimepoints': [at.to_dict() for at in self.activityTimepoints],
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Timeline':
        return cls(
            activities=[Activity.from_dict(a) for a in data.get('activities', [])],
            plannedTimepoints=[PlannedTimepoint.from_dict(pt) for pt in data.get('plannedTimepoints', [])],
            encounters=[Encounter.from_dict(e) for e in data.get('encounters', [])],
            epochs=[Epoch.from_dict(e) for e in data.get('epochs', [])],
            activityGroups=[ActivityGroup.from_dict(g) for g in data.get('activityGroups', [])],
            activityTimepoints=[ActivityTimepoint.from_dict(at) for at in data.get('activityTimepoints', [])],
        )


def create_wrapper_input(timeline: Timeline, usdm_version: str = "4.0", 
                         system_name: str = "Protocol2USDM", 
                         system_version: str = "0.1.0") -> Dict[str, Any]:
    """
    Create a complete USDM Wrapper-Input structure.
    
    Args:
        timeline: Timeline containing all SoA entities
        usdm_version: USDM schema version
        system_name: Name of the generating system
        system_version: Version of the generating system
    
    Returns:
        Complete Wrapper-Input dict ready for JSON serialization
    """
    return {
        'usdmVersion': usdm_version,
        'systemName': system_name,
        'systemVersion': system_version,
        'study': {
            'versions': [{
                'timeline': timeline.to_dict()
            }]
        }
    }
