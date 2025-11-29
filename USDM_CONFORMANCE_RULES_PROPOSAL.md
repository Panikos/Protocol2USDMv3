# USDM Conformance Rules Proposal

**Date:** 2025-11-29  
**Submitted by:** Protocol2USDM Project  
**USDM Version:** 4.0  
**Category:** Completeness & Content Validation  

---

## Executive Summary

During implementation of a protocol-to-USDM extraction pipeline, we identified several cases where USDM documents could be structurally valid (passing schema validation) but semantically incomplete. The current USDM 4.0 rule set focuses primarily on structural validation (e.g., unique identifiers, required references) but lacks rules to verify that essential clinical trial content is present.

We propose a set of **Completeness Conformance Rules** to catch these gaps.

---

## Problem Statement

A USDM document can pass all existing CORE rules while missing critical content such as:

| Missing Content | Impact |
|-----------------|--------|
| Study Identifiers | Cannot link to registries (ClinicalTrials.gov, EudraCT) |
| Objectives & Endpoints | No way to understand study goals |
| Eligibility Criteria | Cannot determine who can participate |
| Study Arms | Cannot understand treatment groups |
| Schedule of Activities | No operational timeline |

These gaps make the USDM document technically valid but practically unusable for downstream systems (CTMS, EDC, regulatory submissions).

---

## Proposed Conformance Rules

### Category 1: Study Identification

#### USDM-COMP-001: Study Must Have Registry Identifier
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-001 |
| **Severity** | Warning |
| **Description** | A Study should have at least one StudyIdentifier linked to a recognized registry (e.g., ClinicalTrials.gov, EudraCT, ISRCTN). |
| **Entities** | StudyVersion, StudyIdentifier |
| **Rationale** | Registry identifiers enable traceability and public disclosure compliance. |
| **Condition** | `study.versions[*].studyIdentifiers` should contain at least one identifier where `scopeId` references an organization with a recognized registry type. |

#### USDM-COMP-002: Study Must Have Protocol Number
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-002 |
| **Severity** | Error |
| **Description** | A Study must have at least one StudyIdentifier representing the sponsor's protocol number. |
| **Entities** | StudyVersion, StudyIdentifier |
| **Rationale** | The protocol number is the primary identifier used by sponsors and regulators. |
| **Condition** | `study.versions[*].studyIdentifiers` must contain at least one identifier. |

---

### Category 2: Objectives & Endpoints

#### USDM-COMP-010: Study Must Have Primary Objective
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-010 |
| **Severity** | Error |
| **Description** | A StudyDesign must have at least one Objective with level code "Primary". |
| **Entities** | StudyDesign, Objective |
| **Rationale** | Every clinical trial must have a defined primary objective. This is required by ICH E6(R2) and regulatory submissions. |
| **Condition** | `study.versions[*].studyDesigns[*].objectives` must contain at least one Objective where `level.code` = "Primary". |

#### USDM-COMP-011: Primary Objective Must Have Endpoint
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-011 |
| **Severity** | Error |
| **Description** | Every primary Objective should have at least one linked Endpoint. |
| **Entities** | Objective, Endpoint |
| **Rationale** | Objectives without measurable endpoints cannot be evaluated. |
| **Condition** | For each Objective where `level.code` = "Primary", `endpointIds` should not be empty OR there should be at least one Endpoint with matching `objectiveId`. |

#### USDM-COMP-012: Endpoint Must Have Description
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-012 |
| **Severity** | Warning |
| **Description** | Every Endpoint should have a non-empty text description. |
| **Entities** | Endpoint |
| **Rationale** | Endpoints without descriptions cannot be operationalized. |
| **Condition** | `endpoint.text` should not be null or empty. |

---

### Category 3: Eligibility Criteria

#### USDM-COMP-020: Study Must Have Eligibility Criteria
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-020 |
| **Severity** | Error |
| **Description** | A StudyDesign must have at least one EligibilityCriterion. |
| **Entities** | StudyDesign, EligibilityCriterion |
| **Rationale** | Every clinical trial must define who can participate. |
| **Condition** | `study.versions[*].studyDesigns[*].eligibilityCriteria` must not be empty. |

#### USDM-COMP-021: Must Have Inclusion Criteria
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-021 |
| **Severity** | Error |
| **Description** | A StudyDesign must have at least one EligibilityCriterion with category "Inclusion". |
| **Entities** | StudyDesign, EligibilityCriterion |
| **Rationale** | Inclusion criteria define the target population. |
| **Condition** | `eligibilityCriteria` must contain at least one criterion where `category.code` = "Inclusion". |

#### USDM-COMP-022: Must Have Exclusion Criteria
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-022 |
| **Severity** | Warning |
| **Description** | A StudyDesign should have at least one EligibilityCriterion with category "Exclusion". |
| **Entities** | StudyDesign, EligibilityCriterion |
| **Rationale** | Most clinical trials have exclusion criteria for safety. |
| **Condition** | `eligibilityCriteria` should contain at least one criterion where `category.code` = "Exclusion". |

#### USDM-COMP-023: Criteria Must Have Text
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-023 |
| **Severity** | Error |
| **Description** | Every EligibilityCriterion must have a linked EligibilityCriterionItem with non-empty text. |
| **Entities** | EligibilityCriterion, EligibilityCriterionItem |
| **Rationale** | Criteria without text cannot be evaluated. |
| **Condition** | For each EligibilityCriterion, `criterionItemId` should reference an EligibilityCriterionItem where `text` is not null or empty. |

---

### Category 4: Study Design Structure

#### USDM-COMP-030: Study Must Have Study Design
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-030 |
| **Severity** | Error |
| **Description** | A StudyVersion must have at least one StudyDesign. |
| **Entities** | StudyVersion, StudyDesign |
| **Rationale** | The study design is the core of the protocol. |
| **Condition** | `study.versions[*].studyDesigns` must not be empty. |

#### USDM-COMP-031: Interventional Study Must Have Arm
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-031 |
| **Severity** | Error |
| **Description** | An interventional StudyDesign must have at least one StudyArm. |
| **Entities** | StudyDesign, StudyArm |
| **Rationale** | Interventional studies must define treatment groups. |
| **Condition** | If `studyDesign.trialType` = "Interventional", then `studyDesign.arms` must not be empty. |

#### USDM-COMP-032: Study Should Have Epochs
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-032 |
| **Severity** | Warning |
| **Description** | A StudyDesign should have at least one Epoch (e.g., Screening, Treatment, Follow-up). |
| **Entities** | StudyDesign, Epoch |
| **Rationale** | Epochs define the major phases of a study. |
| **Condition** | `studyDesign.epochs` should not be empty. |

---

### Category 5: Schedule of Activities

#### USDM-COMP-040: Study Must Have Schedule Timeline
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-040 |
| **Severity** | Error |
| **Description** | A StudyDesign must have at least one ScheduleTimeline. |
| **Entities** | StudyDesign, ScheduleTimeline |
| **Rationale** | The schedule of activities is essential for study operations. |
| **Condition** | `studyDesign.scheduleTimelines` must not be empty. |

#### USDM-COMP-041: Timeline Must Have Activities
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-041 |
| **Severity** | Error |
| **Description** | A ScheduleTimeline must define at least one Activity. |
| **Entities** | StudyDesign, Activity |
| **Rationale** | A timeline without activities has no operational value. |
| **Condition** | `studyDesign.activities` must not be empty. |

#### USDM-COMP-042: Timeline Must Have Encounters
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-042 |
| **Severity** | Error |
| **Description** | A ScheduleTimeline must define at least one Encounter (visit). |
| **Entities** | StudyDesign, Encounter |
| **Rationale** | A timeline without visits has no operational value. |
| **Condition** | `studyDesign.encounters` must not be empty. |

#### USDM-COMP-043: Activities Must Be Scheduled
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-043 |
| **Severity** | Warning |
| **Description** | Every Activity should appear in at least one ScheduledActivityInstance. |
| **Entities** | Activity, ScheduledActivityInstance |
| **Rationale** | Unscheduled activities are not operationally useful. |
| **Condition** | For each Activity in `studyDesign.activities`, there should be at least one ScheduledActivityInstance in `scheduleTimelines[*].instances` with matching `activityId`. |

---

### Category 6: Interventions

#### USDM-COMP-050: Interventional Study Must Have Intervention
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-050 |
| **Severity** | Error |
| **Description** | An interventional StudyDesign must have at least one StudyIntervention. |
| **Entities** | StudyDesign, StudyIntervention |
| **Rationale** | Interventional studies must define what is being tested. |
| **Condition** | If `studyDesign.trialType` = "Interventional", then `studyDesign.studyInterventions` must not be empty. |

#### USDM-COMP-051: Drug Study Must Have Product
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-051 |
| **Severity** | Warning |
| **Description** | A drug study should have at least one AdministrableProduct with dose form and strength. |
| **Entities** | AdministrableProduct |
| **Rationale** | Drug products need complete information for manufacturing and administration. |
| **Condition** | For drug studies, at least one AdministrableProduct should have non-empty `doseForm` and `strength`. |

---

### Category 7: Metadata Completeness

#### USDM-COMP-060: Study Must Have Title
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-060 |
| **Severity** | Error |
| **Description** | A StudyVersion must have at least one StudyTitle. |
| **Entities** | StudyVersion, StudyTitle |
| **Rationale** | Every protocol has a title. |
| **Condition** | `study.versions[*].titles` must not be empty. |

#### USDM-COMP-061: Study Must Have Phase
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-061 |
| **Severity** | Warning |
| **Description** | A StudyVersion should have a studyPhase defined. |
| **Entities** | StudyVersion |
| **Rationale** | Study phase is important for regulatory classification. |
| **Condition** | `study.versions[*].studyPhase` should not be null. |

#### USDM-COMP-062: Study Must Have Sponsor
| Property | Value |
|----------|-------|
| **Rule ID** | USDM-COMP-062 |
| **Severity** | Error |
| **Description** | A Study must have at least one Organization with a sponsor role. |
| **Entities** | Study, Organization |
| **Rationale** | Every clinical trial has a sponsor. |
| **Condition** | `study.organizations` must contain at least one Organization that is referenced as sponsor. |

---

## Implementation Notes

### JSONata Expression Examples

For USDM-COMP-010 (Primary Objective Required):
```jsonata
$count(study.versions.studyDesigns.objectives[level.code = "Primary"]) = 0
```

For USDM-COMP-020 (Eligibility Criteria Required):
```jsonata
$count(study.versions.studyDesigns.eligibilityCriteria) = 0
```

For USDM-COMP-043 (Unscheduled Activities):
```jsonata
(
  $activities := study.versions.studyDesigns.activities.id;
  $scheduled := study.versions.studyDesigns.scheduleTimelines.instances.activityId;
  $activities[$not($ in $scheduled)]
)
```

### Severity Guidelines

- **Error**: Content is required by regulations or makes the document unusable
- **Warning**: Content is expected but may be intentionally omitted in some cases

---

## Benefits

1. **Early Detection**: Catch incomplete USDM documents before downstream processing
2. **Quality Assurance**: Ensure extracted protocols have essential content
3. **Interoperability**: Documents passing these rules will work with CTMS, EDC, and regulatory systems
4. **Guidance**: Rules provide clear expectations for USDM generators

---

## References

- ICH E6(R2) Good Clinical Practice
- ICH E9(R1) Statistical Principles for Clinical Trials
- CDISC USDM 4.0 Specification
- ClinicalTrials.gov Protocol Registration Data Element Definitions

---

## Contact

Protocol2USDM Project  
GitHub: https://github.com/Panikos/Protocol2USDMv3

We welcome feedback and would be happy to contribute JSONata expressions or test data for these rules.
