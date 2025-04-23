import json
import sys
import os

def render_soa_html(soa_path, output_path):
    with open(soa_path, 'r', encoding='utf-8') as f:
        soa = json.load(f)
    html = [
        '<html><head><title>Schedule of Activities Review</title>',
        '<style>body{font-family:sans-serif;} table{border-collapse:collapse;} th,td{border:1px solid #aaa;padding:4px;}</style>',
        '</head><body>',
        '<h1>Schedule of Activities (SoA) - USDM v4.0</h1>'
    ]
    study_name = soa.get('name', 'Unknown Study')
    html.append(f'<h2>Study: {study_name}</h2>')
    # Render timeline
    timeline = soa
    for sv in soa.get('studyVersions', []):
        sd = sv.get('studyDesign', {})
        timeline = sd.get('timeline', {})
        break
    # Support both 'plannedTimepointId' and 'id' for timepoints
    pts_raw = timeline.get('plannedTimepoints', [])
    pts = {}
    for pt in pts_raw:
        ptid = pt.get('plannedTimepointId') or pt.get('id') or pt.get('label')
        if ptid:
            pts[ptid] = pt
    acts = timeline.get('activities', [])
    # Header row
    html.append('<table><tr><th>Activity</th>')
    for ptid in pts:
        pt = pts[ptid]
        label = pt.get('label') or pt.get('timepoint') or ptid
        html.append(f'<th>{label}</th>')
    html.append('</tr>')
    # Activity rows
    for act in acts:
        name = act.get('name') or act.get('description') or act.get('activityId') or act.get('id')
        html.append(f'<tr><td>{name}</td>')
        # Support both 'plannedTimepoints' and 'plannedTimepointIds' or linkage by (activityId,timepointId)
        pts_linked = set()
        for k in ['plannedTimepoints', 'plannedTimepointIds']:
            if k in act:
                pts_linked.update(act[k])
        # Fallback: look for (activityId, plannedTimepointId) linkage in timeline.activityTimepoints
        if not pts_linked and 'activityTimepoints' in timeline:
            for atp in timeline['activityTimepoints']:
                if (atp.get('activityId') == act.get('activityId') or atp.get('activityId') == act.get('id')) and atp.get('plannedTimepointId'):
                    pts_linked.add(atp['plannedTimepointId'])
        for ptid in pts:
            checked = '✔️' if ptid in pts_linked else ''
            html.append(f'<td style="text-align:center">{checked}</td>')
        html.append('</tr>')
    html.append('</table></body></html>')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html))
    print(f"[SUCCESS] Rendered SoA to {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Render SoA JSON to HTML table.")
    parser.add_argument('--soa', default='soa_final.json', help='Path to SoA JSON')
    parser.add_argument('--output', default='soa_final.html', help='Path to output HTML')
    args = parser.parse_args()
    render_soa_html(args.soa, args.output)
