# DarkWing Swift Reporter - Project Requirements Document (PRD)
## 📝 Goal & Scope

The primary objective is to automate a structured, multi-day biological data collection process for Chimney Swifts inhabiting multiple towers (e.g., T1). This system acts as an automated field assistant designed to replace manual observation logging and video review. The final output is not the video reel itself, but a clean, structured digital **System Log** suitable for bulk submission into external forms like the Google Form used by Dr. Kellam.

## 📅 Operational Workflow (The Human Protocol)
The system must strictly adhere to these time-based rules:
1.  **Target Time:** The project runs daily from 6:00 AM to 9:00 PM EDT.
2.  **Sampling Frequency:** Observation checks must occur at $\text{XX}:00$, $\text{XX}:20$, and $\text{XX}:40$. (The system must handle the full range up to $T_{\text{end}}$).
3.  **Look-Ahead Protocol:** For a sampling time $T_{\text{start}}$, the video analysis segment *must* read from $T_{\text{start}}$ to $\mathbf{T_{\text{start}} + 19 \text{ minutes}}$. This is non-negotiable and overrides simple 20-minute blocking.

## <0xF0><0x9F><0x97><0x84>️ Required Data Fields (The System Log Schema)
The final system output must be a CSV/JSON adhering strictly to this schema for each check:

| Field Name | Format | Description | Source / Origin | Notes |
| :--- | :--- | :--- | :--- | :--- |
|| `TOWER_ID` | String | Unique tower identifier (e.g., T1). | Input Config | |
|| `DATE` | YYYY-MM-DD | Date of collection. | System Clock | Must be accurate. |
|| `SAMPLE_TIME` | HH:MM | The time the observation was checked against schedule. | Derived from $T_{\text{start}}$. | This is what gets written to the form's date/time field. |
|| `FIRST_DETECTION_TS` | HH:MM:SS | Timestamp (EDT) of the first required sighting within the scan window. | Live Video & ML Analysis | Null value signifies zero swifts present. |
|| `CONFIDENCE` | Float | The model's numeric confidence score for the detection. | Live Video & ML Analysis | System must record if < 0.7. |
|| `ADULT_COUNT` | Integer | Number of adult Swifts in the chimney (best guess). | Live Video & ML Analysis | |
|| `NESTING_STAGE` | String | Current stage: [None, Building, Egg(s) present, Nestling(s) present, Post-fledgling]. | Advanced AI Processing | |
|| `BILL_ACTIVITY` | String | Actions with bill: [N/A/No, Handling material, Feeding, Tending eggs, Tending nestlings, Preening self, Preening other, Other]. | Advanced AI Processing | |
|| `FLIGHT_EVENTS` | String | Observed movements (max 3 choices): [In, Out, Changed Position within chimney]. | Live Video & ML Analysis | Concat unless only one. |
|| `PROXIMMITY_COUNT` | Integer | Adults within two body-lengths of the nest. | Live Video & ML Analysis | |
|| `AWAKE_STATUS` | String | State: [Yes, No, Maybe, No adults present]. | Live Video & ML Analysis | |
|| `BEHAVIORAL_FLAG`| String | Categorized notes (e.g., "Nest switch", "Visible Eggs"). | Advanced AI Processing | This captures remaining rich, non-numeric data points. |

## 💡 Key Assumption & Scope Limitation
*   **Video Output:** The system will NOT generate the final reel or clip archives automatically. Clipping is an *optional* step for human review only; the core output must be the structured System Log.
*   **Time Zone:** All internal logic and logged data points MUST reference **EDT**.

---
***End of PRD***