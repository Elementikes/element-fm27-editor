from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v7.6 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v7.6 marker missing: {label}")
    return text.replace(old,new,1)

p="src/ui/staff_panel.rs"
t=rd(p)

if "    PowerTools,\n" not in t:
    t=one(t,"    Contract,\n}","    Contract,\n    PowerTools,\n}","StaffTab enum")
    t=one(t,
        '''        if has_contract {
            ui.selectable_value(tab, StaffTab::Contract, "Contract");
        }
''',
        '''        if has_contract {
            ui.selectable_value(tab, StaffTab::Contract, "Contract");
        }
        ui.selectable_value(tab, StaffTab::PowerTools, "Power Tools");
''',
        "Staff Power Tools button")
    t=one(t,
        "        StaffTab::Contract => show_contract(schemas, ui, staff, &mut edits),\n",
        "        StaffTab::Contract => show_contract(schemas, ui, staff, &mut edits),\n        StaffTab::PowerTools => show_staff_power_tools(schemas, ui, staff, &mut edits),\n",
        "Staff Power Tools match")

if "fn show_staff_power_tools(" not in t:
    marker="fn header(\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v7.6 marker missing: header")
    fn=r'''fn push_staff_category_max(
    schemas: &'static crate::fields::VersionedSchemas,
    staff: &mut StaffView,
    category: Category,
    section: &str,
    edits: &mut Vec<FieldEdit>,
) -> usize {
    let mut changed=0usize;
    for f in schemas.fields_for_category(Entity::Staff, category) {
        let Some(loc)=f.offset else { continue; };
        // RoleIndex / pointer / string rows are never touched by this preset.
        if matches!(loc.encoding(), crate::fields::Encoding::Pointer | crate::fields::Encoding::FmString | crate::fields::Encoding::RoleIndex | crate::fields::Encoding::F32Raw) { continue; }
        let off=loc.offset() as usize;
        let Some(&old)=staff.record.raw.get(off) else {continue;};
        let displayed=loc.decode_u8(old);
        if !(1..=20).contains(&displayed) || displayed==20 {continue;}
        let new=loc.encode_u8(20);
        staff.record.raw[off]=new;
        edits.push(FieldEdit{
            addr: staff.record.addr+loc.offset(),
            old_raw:vec![old],
            new_raw:vec![new],
            description:format!("Staff {} • {}: {} → 20",section,f.label,displayed),
            presentation:None,
        });
        changed+=1;
    }
    changed
}

fn push_staff_ca_pa(
    schemas: &'static crate::fields::VersionedSchemas,
    staff: &mut StaffView,
    edits: &mut Vec<FieldEdit>,
) -> usize {
    let mut changed=0usize;
    for (key,label) in [("s_ca","Current Ability"),("s_pa","Potential Ability")] {
        let Some(f)=schemas.field(key) else{continue;};
        let Some(loc)=f.offset else{continue;};
        let off=loc.offset() as usize;
        if off+2>staff.record.raw.len(){continue;}
        let old_raw=staff.record.raw[off..off+2].to_vec();
        let old=u16::from_le_bytes([old_raw[0],old_raw[1]]);
        if old==200 {continue;}
        let new_raw=200u16.to_le_bytes().to_vec();
        staff.record.raw[off..off+2].copy_from_slice(&new_raw);
        edits.push(FieldEdit{
            addr:staff.record.addr+loc.offset(),old_raw,new_raw,
            description:format!("Staff {label}: {old} → 200"),presentation:None,
        });
        changed+=1;
    }
    changed
}

fn show_staff_power_tools(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    staff: &mut StaffView,
    edits: &mut Vec<FieldEdit>,
) {
    ui.horizontal_wrapped(|ui|{
        ui.heading("Staff Power Tools");
        ui.label(egui::RichText::new("ELEMENT v7.6 • VERIFIED PRESETS").strong().color(egui::Color32::from_rgb(116,145,255)));
    });
    ui.label(egui::RichText::new("Only mapped staff attributes already exposed by the current FM27 editor are bulk-set. Human-manager identity shifts are handled by the existing guarded edit redirect.").weak());
    ui.add_space(8.0);
    let enabled=crate::ui::navigation::editing_enabled(ui);
    egui::Grid::new(("element_v7_staff_power",staff.record.addr)).num_columns(2).spacing([10.0,8.0]).show(ui,|ui|{
        if ui.add_enabled(enabled,egui::Button::new("🎓 COACHING • 20")).clicked(){push_staff_category_max(schemas,staff,Category::Coaching,"Coaching",edits);}
        if ui.add_enabled(enabled,egui::Button::new("🧠 MENTAL • 20")).clicked(){push_staff_category_max(schemas,staff,Category::Mental,"Mental",edits);}
        ui.end_row();
        if ui.add_enabled(enabled,egui::Button::new("🔎 KNOWLEDGE • 20")).clicked(){push_staff_category_max(schemas,staff,Category::Knowledge,"Knowledge",edits);}
        if ui.add_enabled(enabled,egui::Button::new("🩺 MEDICAL • 20")).clicked(){push_staff_category_max(schemas,staff,Category::Medical,"Medical",edits);}
        ui.end_row();
        if ui.add_enabled(enabled,egui::Button::new("⭐ CA / PA • 200 / 200")).clicked(){push_staff_ca_pa(schemas,staff,edits);}
        if ui.add_enabled(enabled,egui::Button::new("🔥 ELITE STAFF")).clicked(){
            for (cat,label) in [(Category::Coaching,"Coaching"),(Category::Mental,"Mental"),(Category::Knowledge,"Knowledge"),(Category::Medical,"Medical")]{push_staff_category_max(schemas,staff,cat,label,edits);}
            push_staff_ca_pa(schemas,staff,edits);
        }
        ui.end_row();
    });
    ui.add_space(12.0);ui.separator();
    ui.strong("Manual / read-only semantics");
    ui.label("Tactical Style, Board Relations and Personality stay manual: values such as Dirtiness or Interference are not universally better at 20.");
    ui.label("Role Ratings, Languages, Coaching Licence and Preferred Formations stay read-only until their write semantics are independently certified on FM27.");
}

'''
    t=t[:idx]+fn+t[idx:]
wr(p,t)
print("Element v7.6 Staff Power Tools applied.")
