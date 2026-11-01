from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v7.7 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v7.7 marker missing: {label}")
    return text.replace(old,new,1)

p="src/ui/club_panel.rs"
t=rd(p)

if "fn element_club_set_u8(" not in t:
    marker="fn show_power_tools(\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v7.7 marker missing: show_power_tools")
    helpers=r'''fn element_club_set_u8(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    key: &str,
    value: u8,
    label: &str,
    edits: &mut Vec<FieldEdit>,
) -> bool {
    let Some((container,offset))=sub_location(schemas,key) else{return false;};
    let Some((buf,base))=club.sub_record_mut(container) else{return false;};
    let Some(&old)=buf.get(offset) else{return false;};
    if old==value{return false;}
    buf[offset]=value;
    edits.push(FieldEdit{addr:base+offset as u64,old_raw:vec![old],new_raw:vec![value],description:format!("{label}: {old} → {value}"),presentation:None});
    true
}

fn element_club_set_u16(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    key: &str,
    value: u16,
    label: &str,
    edits: &mut Vec<FieldEdit>,
) -> bool {
    let Some((container,offset))=sub_location(schemas,key) else{return false;};
    let Some((buf,base))=club.sub_record_mut(container) else{return false;};
    if offset+2>buf.len(){return false;}
    let old_raw=buf[offset..offset+2].to_vec();
    let old=u16::from_le_bytes([old_raw[0],old_raw[1]]);
    if old==value{return false;}
    let new_raw=value.to_le_bytes().to_vec();
    buf[offset..offset+2].copy_from_slice(&new_raw);
    edits.push(FieldEdit{addr:base+offset as u64,old_raw,new_raw,description:format!("{label}: {old} → {value}"),presentation:None});
    true
}

fn element_club_set_u32(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    key: &str,
    value: u32,
    label: &str,
    edits: &mut Vec<FieldEdit>,
) -> bool {
    let Some((container,offset))=sub_location(schemas,key) else{return false;};
    let Some((buf,base))=club.sub_record_mut(container) else{return false;};
    if offset+4>buf.len(){return false;}
    let old_raw=buf[offset..offset+4].to_vec();
    let old=u32::from_le_bytes(old_raw.as_slice().try_into().unwrap());
    if old==value{return false;}
    let new_raw=value.to_le_bytes().to_vec();
    buf[offset..offset+4].copy_from_slice(&new_raw);
    edits.push(FieldEdit{addr:base+offset as u64,old_raw,new_raw,description:format!("{label}: {old} → {value}"),presentation:None});
    true
}

fn element_max_facilities(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) -> usize {
    let mut n=0usize;
    for (label,key) in [
        ("Training","c_training"),
        ("Youth Facilities","c_youth_fac"),
        ("Youth Improvement","c_youth_improve"),
        ("Youth Coaching","c_youth_coach"),
        ("Youth Recruitment","c_youth_recruit"),
        ("Corporate","c_corporate"),
    ] {
        if element_club_set_u8(schemas,club,key,20,label,edits){n+=1;}
        let mirror=format!("{key}_fin");
        if element_club_set_u8(schemas,club,&mirror,20,&format!("{label} (finance mirror)"),edits){n+=1;}
    }
    n
}

'''
    t=t[:idx]+helpers+t[idx:]

if "CLUB POWER • VERIFIED FIELDS" not in t:
    marker='''    ui.add_space(12.0);
    ui.separator();
    ui.strong("Intentionally locked until independently mapped");
'''
    block=r'''    ui.add_space(12.0);
    ui.separator();
    ui.horizontal_wrapped(|ui| {
        ui.strong("CLUB POWER • VERIFIED FIELDS");
        ui.label(egui::RichText::new("reputation • facilities • finance").small().weak());
    });
    ui.label(egui::RichText::new("These presets use the same current-FM27 fields as the individual Overview / Facilities / Finance controls and still enter Change History / Undo.").weak());
    ui.add_space(5.0);
    ui.horizontal_wrapped(|ui| {
        if ui.add_enabled(writable,egui::Button::new("🏆 REPUTATION • 10000")).clicked(){
            element_club_set_u16(club.build.schemas(),club,"c_reputation",10_000,"Club Reputation",edits);
        }
        if ui.add_enabled(writable,egui::Button::new("🏗 MAX FACILITIES • 20")).clicked(){
            element_max_facilities(club.build.schemas(),club,edits);
        }
        if ui.add_enabled(writable,egui::Button::new("💷 RICH CLUB • £1B")).clicked(){
            element_club_set_u32(club.build.schemas(),club,"c_balance",1_000_000_000,"Balance",edits);
            element_club_set_u32(club.build.schemas(),club,"c_transfer_budget",500_000_000,"Transfer Budget",edits);
            element_club_set_u32(club.build.schemas(),club,"c_transfer_remaining",500_000_000,"Transfer Remaining",edits);
        }
        if ui.add_enabled(writable,egui::Button::new("🔥 MAX CLUB CORE")).clicked(){
            element_club_set_u16(club.build.schemas(),club,"c_reputation",10_000,"Club Reputation",edits);
            element_max_facilities(club.build.schemas(),club,edits);
            element_club_set_u32(club.build.schemas(),club,"c_balance",1_000_000_000,"Balance",edits);
            element_club_set_u32(club.build.schemas(),club,"c_transfer_budget",500_000_000,"Transfer Budget",edits);
            element_club_set_u32(club.build.schemas(),club,"c_transfer_remaining",500_000_000,"Transfer Remaining",edits);
        }
    });
    ui.label(egui::RichText::new("Stadium capacity, supporter profile and derived wage totals remain read-only because the current engine does not expose them as verified writable fields.").small().weak());

    ui.add_space(12.0);
    ui.separator();
    ui.strong("Intentionally locked until independently mapped");
'''
    t=one(t,marker,block,"club power block")

wr(p,t)
print("Element v7.7 Club Power Tools applied.")
