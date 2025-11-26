Relevant USDM 4.0 Entities for Schedule of Activities
1. PlannedTimepoint
Definition: Represents specific timepoints when activities occur.

Example: "Day 1", "Week 4", "Screening (-42 to -9)", "EOS Visit"

Key Attributes:

id

name

description

DDF-RA Source: /PlannedTimepoint.json

2. Activity
Definition: A discrete clinical or operational task performed at a timepoint.

Example: "Informed Consent", "Physical Exam", "Blood Draw"

Key Attributes:

id

name

DDF-RA Source: /Activity.json

3. ActivityTimepoint
Definition: The association that maps which activities occur at which timepoints.

Example: "Informed Consent" is performed at "Screening"

Key Attributes:

activityId

plannedTimepointId

DDF-RA Source: /ActivityTimepoint.json

4. ActivityGroup
Definition: Optional grouping of related activities.

Example: "Screening Assessments", "Treatment Phase Activities"

Key Attributes:

id

name

DDF-RA Source: /ActivityGroup.json

5. Encounter
Definition: Represents a visit or visit window.

Example: "Screening Visit", "Baseline Visit", "Follow-Up Visit"

Key Attributes:

id

name

scheduledAt (links to PlannedTimepoints)

DDF-RA Source: /Encounter.json

6. Epoch
Definition: A distinct study phase.

Example: "Screening Epoch", "Treatment Epoch", "Follow-Up Epoch"

Key Attributes:

id

name

type (e.g., Screening, Treatment)

DDF-RA Source: /Epoch.json

7. StudyDesign
Definition: Container that links the full SoA timeline and its components.

Key Relationships:

scheduleOfActivities

encounters

epochs

activities

plannedTimepoints

DDF-RA Source: /StudyDesign.json

8. StudyArm (Contextual)
Definition: Defines parallel groups if applicable.

Example: "Treatment Arm A", "Treatment Arm B"

Usage: Important if SoA differs by arm.

DDF-RA Source: /StudyArm.json

9. StudyElement (Contextual)
Definition: Building blocks of the study timeline that can link Epochs, Activities, and Encounters.

Example: "Inpatient Period", "Outpatient Period"

DDF-RA Source: /StudyElement.json

🔍 Visualizing the SoA Entity Relationships
plaintext
Copy
Edit
StudyDesign
├── PlannedTimepoints
├── Activities
├── ActivityTimepoints (mapping)
├── ActivityGroups (optional)
├── Encounters (visit windows)
└── Epochs (study phases)
✅ Summary Table
Entity	Purpose	DDF-RA Location
PlannedTimepoint	Defines when activities occur	/PlannedTimepoint.json
Activity	Defines what is being done	/Activity.json
ActivityTimepoint	Links activities to timepoints	/ActivityTimepoint.json
ActivityGroup	Optional grouping of activities	/ActivityGroup.json
Encounter	Defines visit windows or visits	/Encounter.json
Epoch	Defines study phases	/Epoch.json
StudyDesign	Central structure of SoA	/StudyDesign.json
StudyArm	Defines treatment groups	/StudyArm.json
StudyElement	Defines study sequence components	/StudyElement.json