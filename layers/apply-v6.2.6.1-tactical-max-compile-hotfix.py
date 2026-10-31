from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.2.6.1 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.2.6.1 marker missing: {label}")
    return text.replace(old, new, 1)

# Keep the prepared Tactical MAX plan on ClubView rather than trying to push it
# through an egui Context from the bridge-result handler (which has no ctx in scope).
cmd_path = "src/bridge/cmd.rs"
cmd = rd(cmd_path)
if "pub tactical_max_plan: Option<TacticalMaxPlan>" not in cmd:
    cmd = one(
        cmd,
        "    pub tactical_report: Option<TacticalInspectorReport>,\n",
        "    pub tactical_report: Option<TacticalInspectorReport>,\n    pub tactical_max_plan: Option<TacticalMaxPlan>,\n",
        "ClubView tactical plan field",
    )
wr(cmd_path, cmd)

entity_path = "src/bridge/entity_load.rs"
entity = rd(entity_path)
if "tactical_max_plan: None" not in entity:
    entity = one(
        entity,
        "        tactical_report: None,\n",
        "        tactical_report: None,\n        tactical_max_plan: None,\n",
        "ClubView tactical plan init",
    )
wr(entity_path, entity)

# Make the tactical page mutable so it can take() a prepared plan exactly once.
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
club = one(
    club,
    "fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView, edits: &mut Vec<FieldEdit>) {",
    "fn show_tactical_understanding(ui: &mut egui::Ui, club: &mut ClubView, edits: &mut Vec<FieldEdit>) {",
    "mutable tactical page",
)
old_consumer = r'''    let plan_id = egui::Id::new(("element_tactical_max_plan", club.addr));
    if let Some(plan) = ui.ctx().data_mut(|d| {
        let p = d.get_temp::<crate::bridge::TacticalMaxPlan>(plan_id);
        d.remove::<crate::bridge::TacticalMaxPlan>(plan_id);
        p
    }) {
        for p in plan.edits {
            edits.push(FieldEdit {
                addr: p.addr,
                old_raw: p.old_raw,
                new_raw: p.new_raw,
                description: p.description,
            });
        }
    }
'''
new_consumer = r'''    if let Some(plan) = club.tactical_max_plan.take() {
        for p in plan.edits {
            edits.push(FieldEdit {
                addr: p.addr,
                old_raw: p.old_raw,
                new_raw: p.new_raw,
                description: p.description,
            });
        }
    }
'''
club = one(club, old_consumer, new_consumer, "ClubView plan consumer")
wr(club_path, club)

# Publish the worker's prepared plan into both the selected club and its snapshot,
# mirroring the already-proven TacticalInspectorDone plumbing.
app_path = "src/app.rs"
app = rd(app_path)
old_arm = r'''                BridgeResult::TacticalMaxPlanReady { club_addr, plan } => {
                    let summary = format!(
                        "Tactical MAX prepared: {} First Team players, {} edits ({} instruction entries, {} formation/role rows)",
                        plan.players_matched, plan.edits.len(), plan.instruction_entries, plan.formation_rows,
                    );
                    ctx.data_mut(|d| d.insert_temp(
                        egui::Id::new(("element_tactical_max_plan", club_addr)),
                        plan,
                    ));
                    self.set_status(summary);
                }
'''
new_arm = r'''                BridgeResult::TacticalMaxPlanReady { club_addr, plan } => {
                    let summary = format!(
                        "Tactical MAX prepared: {} First Team players, {} edits ({} instruction entries, {} formation/role rows)",
                        plan.players_matched, plan.edits.len(), plan.instruction_entries, plan.formation_rows,
                    );
                    if let Some(snapshot) = self.club_snapshots.get_mut(&club_addr) {
                        snapshot.tactical_max_plan = Some(plan.clone());
                    }
                    if let Some(club) = self.selected_club.as_mut().filter(|c| c.addr == club_addr) {
                        club.tactical_max_plan = Some(plan);
                    }
                    self.set_status(summary);
                }
'''
app = one(app, old_arm, new_arm, "bridge result plan storage")
wr(app_path, app)

print("Element v6.2.6.1 Tactical MAX compile hotfix applied.")
