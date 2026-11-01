from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v8.2 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v8.2 marker missing: {label}")
    return text.replace(old, new, 1)

# -----------------------------------------------------------------------------
# PLAYER FULL WRITE DECK
# Uses only fields already certified by Element/FM27 mappings. Every write emits
# FieldEdit so the normal expected-byte Change History / Undo pipeline applies.
# -----------------------------------------------------------------------------
p = "src/ui/player_panel.rs"
t = rd(p)

if "fn push_category_value_v82(" not in t:
    marker = "fn push_ca_pa_max(\n"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v8.2 player helper marker missing")
    helper = r'''fn push_category_value_v82(
    schemas: &'static fields::VersionedSchemas,
    player: &mut PlayerRecord,
    addr: u64,
    category: Category,
    value: u8,
    label: &str,
    edits: &mut Vec<FieldEdit>,
) -> usize {
    let value=value.clamp(1,20);
    let mut changed=0usize;
    for f in schemas.fields_for_category(Entity::Player,category) {
        let Some(loc)=f.offset else{continue;};
        if matches!(loc.encoding(),fields::Encoding::Pointer|fields::Encoding::FmString|fields::Encoding::RoleIndex|fields::Encoding::F32Raw){continue;}
        let off=loc.offset() as usize;
        let Some(&old)=player.raw.get(off) else{continue;};
        let displayed=loc.decode_u8(old);
        if !(1..=20).contains(&displayed){continue;}
        let new=loc.encode_u8(value);
        if old==new{continue;}
        player.raw[off]=new;
        let physical=addr+player::player_phys_offset(schemas,loc.offset(),player.person_shift);
        edits.push(FieldEdit{addr:physical,old_raw:vec![old],new_raw:vec![new],description:format!("{label} • {}: {displayed} → {value}",f.label),presentation:None});
        changed+=1;
    }
    changed
}

fn set_player_u16_v82(
    schemas:&'static fields::VersionedSchemas,
    player:&mut PlayerRecord,
    addr:u64,
    key:&str,
    value:u16,
    label:&str,
    edits:&mut Vec<FieldEdit>,
)->bool{
    let Some(field)=schemas.field(key) else{return false;};
    let Some(loc)=field.offset else{return false;};
    let off=loc.offset() as usize;
    if off+2>player.raw.len(){return false;}
    let old_raw=player.raw[off..off+2].to_vec();
    let old=u16::from_le_bytes([old_raw[0],old_raw[1]]);
    let value=value.clamp(1,200);
    if old==value{return false;}
    let new_raw=value.to_le_bytes().to_vec();
    player.raw[off..off+2].copy_from_slice(&new_raw);
    let physical=addr+player::player_phys_offset(schemas,loc.offset(),player.person_shift);
    edits.push(FieldEdit{addr:physical,old_raw,new_raw,description:format!("{label}: {old} → {value}"),presentation:None});
    true
}

'''
    t = t[:idx] + helper + t[idx:]

if "ELEMENT v8.2 • FULL WRITE DECK" not in t:
    anchor = '''    ui.add_space(12.0);
    ui.separator();
    ui.strong("Manual / semantic fields");
'''
    block = r'''    ui.add_space(12.0);
    ui.separator();
    ui.horizontal_wrapped(|ui|{
        ui.strong("ELEMENT v8.2 • FULL WRITE DECK");
        ui.label(egui::RichText::new("custom mapped writes • add / remove safe status • undoable").small().weak());
    });
    ui.label(egui::RichText::new("Set any mapped attribute family to an exact value instead of only MAX. Pointer/string/list records are excluded automatically.").weak());

    let value_id=egui::Id::new(("v82_player_attr_value",player.addr));
    let mut value=ui.ctx().data(|d|d.get_temp::<u8>(value_id).unwrap_or(15));
    ui.horizontal_wrapped(|ui|{
        ui.label("Attribute value");
        ui.add(egui::Slider::new(&mut value,1..=20).show_value(true));
        if ui.add_enabled(enabled,egui::Button::new("Technical + Set Pieces")).clicked(){push_category_value_v82(schemas,player,addr,Category::Technical,value,"Technical",edits);push_category_value_v82(schemas,player,addr,Category::SetPieces,value,"Set Pieces",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Mental")).clicked(){push_category_value_v82(schemas,player,addr,Category::Mental,value,"Mental",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Physical")).clicked(){push_category_value_v82(schemas,player,addr,Category::Physical,value,"Physical",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Goalkeeping")).clicked(){push_category_value_v82(schemas,player,addr,Category::Goalkeeping,value,"Goalkeeping",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Positions")).clicked(){push_category_value_v82(schemas,player,addr,Category::Positions,value,"Positions",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Both feet")).clicked(){push_category_value_v82(schemas,player,addr,Category::Footedness,value,"Footedness",edits);}
    });
    ui.ctx().data_mut(|d|d.insert_temp(value_id,value));
    ui.horizontal_wrapped(|ui|{
        if ui.add_enabled(enabled,egui::Button::new("NORMALIZE CORE → 10")).clicked(){for (cat,label) in [(Category::Technical,"Technical"),(Category::SetPieces,"Set Pieces"),(Category::Mental,"Mental"),(Category::Physical,"Physical"),(Category::Goalkeeping,"Goalkeeping")]{push_category_value_v82(schemas,player,addr,cat,10,label,edits);}}
        if ui.add_enabled(enabled,egui::Button::new("SET SELECTED CORE VALUE")).clicked(){for (cat,label) in [(Category::Technical,"Technical"),(Category::SetPieces,"Set Pieces"),(Category::Mental,"Mental"),(Category::Physical,"Physical"),(Category::Goalkeeping,"Goalkeeping")]{push_category_value_v82(schemas,player,addr,cat,value,label,edits);}}
    });

    let ca_id=egui::Id::new(("v82_player_ca",player.addr));let pa_id=egui::Id::new(("v82_player_pa",player.addr));
    let mut ca=ui.ctx().data(|d|d.get_temp::<u16>(ca_id).unwrap_or(player.field_u16("p_ca").unwrap_or(100).clamp(1,200)));
    let mut pa=ui.ctx().data(|d|d.get_temp::<u16>(pa_id).unwrap_or(player.field_u16("p_pa").unwrap_or(100).clamp(1,200)));
    ui.horizontal_wrapped(|ui|{
        ui.label("CA");ui.add(egui::DragValue::new(&mut ca).range(1..=200));
        ui.label("PA");ui.add(egui::DragValue::new(&mut pa).range(1..=200));
        if ui.add_enabled(enabled,egui::Button::new("APPLY CA / PA")).clicked(){set_player_u16_v82(schemas,player,addr,"p_ca",ca,"Current Ability",edits);set_player_u16_v82(schemas,player,addr,"p_pa",pa,"Potential Ability",edits);}
    });
    ui.ctx().data_mut(|d|{d.insert_temp(ca_id,ca);d.insert_temp(pa_id,pa);});

    let morale_id=egui::Id::new(("v82_player_morale",player.addr));let mut morale=ui.ctx().data(|d|d.get_temp::<u8>(morale_id).unwrap_or(player.field_u8("p_morale").unwrap_or(10).clamp(1,20)));
    ui.horizontal_wrapped(|ui|{
        ui.label("Morale");ui.add(egui::Slider::new(&mut morale,1..=20));
        if ui.add_enabled(enabled,egui::Button::new("APPLY MORALE")).clicked(){set_morale_v81(schemas,player,addr,morale,edits);}
        if ui.add_enabled(enabled,egui::Button::new("REMOVE ALL INJURIES")).clicked(){heal_all_v81(player,edits);}
        if ui.add_enabled(enabled,egui::Button::new("REMOVE ALL BANS")).clicked(){lift_all_bans_v81(schemas,player,edits);}
    });
    ui.ctx().data_mut(|d|d.insert_temp(morale_id,morale));

    ui.label(egui::RichText::new("Hidden / Personality remain manual because high is not always good. Injuries and bans are REMOVE operations on the verified list/date chain; creating new list records is still blocked until allocation semantics are certified.").small().weak());

    ui.add_space(12.0);
    ui.separator();
    ui.strong("Manual / semantic fields");
'''
    t = one(t, anchor, block, "player v8.2 write deck")

# Improve the native-map status copy with concrete FMRTE-discovered targets.
if "AddWorkPermit / PlayerWorkPermits" not in t:
    t=t.replace(
        'ui.add_space(8.0);ui.strong("Native FM27 chain");ui.label("IL2CPP exposes WorkPermitReference / WorkPermitExempt, but nation-specific rule evaluation and the writable player permit record are not independently certified yet. This page intentionally avoids a fake Grant/Exempt write.");',
        'ui.add_space(8.0);ui.strong("Native FM27 chain");ui.label("FMRTE 27 exposes AddWorkPermit / PlayerWorkPermits and FM27 metadata exposes WorkPermitReference / WorkPermitExempt. Element has the semantic target, but the writable permit-list allocation/removal chain is not yet independently certified, so no fake Grant/Remove button is exposed.");',1)
if "ActiveUnhappinessMotives" not in t:
    t=t.replace(
        'ui.add_space(8.0);ui.strong("Native promises / happiness");ui.label("FM27 metadata exposes PromiseReference, PlayerHasActivePromiseTarget, PlayerWaitingOnPromiseForHappiness and PlayerRemoveAllUnhappiness. Their object chain and rollback semantics are not independently mapped yet, so Element only applies the verified morale component here.");',
        'ui.add_space(8.0);ui.strong("Native promises / happiness");ui.label("FMRTE 27 exposes ActiveUnhappinessMotives, Add/ClearUnhappinessMotives and Promises; FM27 exposes PromiseReference / PlayerRemoveAllUnhappiness. Element applies verified Morale writes now, while promise-list allocation/removal stays locked until read-back/rollback semantics are mapped.");',1)
if "IsRetiring / RetireDate" not in t:
    t=t.replace(
        'ui.add_space(8.0);ui.label("FM27 exposes PlayerRetiring / PlayerRetired concepts, but the player retirement date/state storage is not certified. Set/Clear Retirement remains write-locked rather than guessing a byte.");',
        'ui.add_space(8.0);ui.label("FMRTE 27 exposes IsRetiring / RetireDate / Retirement, and FM27 exposes PlayerRetiring / PlayerRetired concepts. The concrete reversible date/state record is not certified yet, so Set/Clear Retirement remains write-locked rather than guessing a byte.");',1)

wr(p,t)

# -----------------------------------------------------------------------------
# STAFF FULL WRITE DECK
# -----------------------------------------------------------------------------
p="src/ui/staff_panel.rs";t=rd(p)
if "fn push_staff_category_value_v82(" not in t:
    marker="fn push_staff_ca_pa(\n";idx=t.find(marker)
    if idx<0:raise SystemExit("v8.2 staff helper marker missing")
    helper=r'''fn push_staff_category_value_v82(
    schemas:&'static crate::fields::VersionedSchemas,
    staff:&mut StaffView,
    category:Category,
    value:u8,
    section:&str,
    edits:&mut Vec<FieldEdit>,
)->usize{
    let value=value.clamp(1,20);let mut changed=0usize;
    for f in schemas.fields_for_category(Entity::Staff,category){
        let Some(loc)=f.offset else{continue;};
        if matches!(loc.encoding(),crate::fields::Encoding::Pointer|crate::fields::Encoding::FmString|crate::fields::Encoding::RoleIndex|crate::fields::Encoding::F32Raw){continue;}
        let off=loc.offset() as usize;let Some(&old)=staff.record.raw.get(off) else{continue;};let displayed=loc.decode_u8(old);
        if !(1..=20).contains(&displayed){continue;}let new=loc.encode_u8(value);if old==new{continue;}staff.record.raw[off]=new;
        edits.push(FieldEdit{addr:staff.record.addr+loc.offset(),old_raw:vec![old],new_raw:vec![new],description:format!("Staff {section} • {}: {displayed} → {value}",f.label),presentation:None});changed+=1;
    }changed
}

'''
    t=t[:idx]+helper+t[idx:]
if "ELEMENT v8.2 • STAFF WRITE DECK" not in t:
    anchor='''    ui.add_space(12.0);ui.separator();
    ui.strong("Manual / read-only semantics");
'''
    block=r'''    ui.add_space(12.0);ui.separator();
    ui.horizontal_wrapped(|ui|{ui.strong("ELEMENT v8.2 • STAFF WRITE DECK");ui.label(egui::RichText::new("exact mapped values").small().weak());});
    let id=egui::Id::new(("v82_staff_value",staff.record.addr));let mut value=ui.ctx().data(|d|d.get_temp::<u8>(id).unwrap_or(15));
    ui.horizontal_wrapped(|ui|{
        ui.label("Value");ui.add(egui::Slider::new(&mut value,1..=20));
        if ui.add_enabled(enabled,egui::Button::new("Coaching")).clicked(){push_staff_category_value_v82(schemas,staff,Category::Coaching,value,"Coaching",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Mental")).clicked(){push_staff_category_value_v82(schemas,staff,Category::Mental,value,"Mental",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Knowledge")).clicked(){push_staff_category_value_v82(schemas,staff,Category::Knowledge,value,"Knowledge",edits);}
        if ui.add_enabled(enabled,egui::Button::new("Medical")).clicked(){push_staff_category_value_v82(schemas,staff,Category::Medical,value,"Medical",edits);}
    });ui.ctx().data_mut(|d|d.insert_temp(id,value));
    ui.horizontal_wrapped(|ui|{
        if ui.add_enabled(enabled,egui::Button::new("NORMALIZE STAFF CORE → 10")).clicked(){for (cat,label) in [(Category::Coaching,"Coaching"),(Category::Mental,"Mental"),(Category::Knowledge,"Knowledge"),(Category::Medical,"Medical")]{push_staff_category_value_v82(schemas,staff,cat,10,label,edits);}}
        if ui.add_enabled(enabled,egui::Button::new("SET ALL CORE TO SELECTED")).clicked(){for (cat,label) in [(Category::Coaching,"Coaching"),(Category::Mental,"Mental"),(Category::Knowledge,"Knowledge"),(Category::Medical,"Medical")]{push_staff_category_value_v82(schemas,staff,cat,value,label,edits);}}
    });
    ui.add_space(12.0);ui.separator();
    ui.strong("Manual / read-only semantics");
'''
    t=one(t,anchor,block,"staff v8.2 write deck")
wr(p,t)

# -----------------------------------------------------------------------------
# CLUB FULL WRITE DECK
# Exact reputation / finance / facilities writes using already-certified helpers.
# -----------------------------------------------------------------------------
p="src/ui/club_panel.rs";t=rd(p)
if "ELEMENT v8.2 • CLUB WRITE DECK" not in t:
    anchor='''    ui.add_space(12.0);
    ui.separator();
    ui.strong("Intentionally locked until independently mapped");
'''
    block=r'''    ui.add_space(12.0);
    ui.separator();
    ui.horizontal_wrapped(|ui|{ui.strong("ELEMENT v8.2 • CLUB WRITE DECK");ui.label(egui::RichText::new("exact reputation • finance • facilities").small().weak());});
    let rep_id=egui::Id::new(("v82_club_rep",club.addr));let bal_id=egui::Id::new(("v82_club_bal",club.addr));let tb_id=egui::Id::new(("v82_club_tb",club.addr));let fac_id=egui::Id::new(("v82_club_fac",club.addr));
    let mut rep=ui.ctx().data(|d|d.get_temp::<u16>(rep_id).unwrap_or(8000));let mut bal=ui.ctx().data(|d|d.get_temp::<u32>(bal_id).unwrap_or(250_000_000));let mut tb=ui.ctx().data(|d|d.get_temp::<u32>(tb_id).unwrap_or(100_000_000));let mut fac=ui.ctx().data(|d|d.get_temp::<u8>(fac_id).unwrap_or(20));
    ui.horizontal_wrapped(|ui|{
        ui.label("Reputation");ui.add(egui::DragValue::new(&mut rep).range(0..=10_000));if ui.add_enabled(writable,egui::Button::new("APPLY REP")).clicked(){element_club_set_u16(club.build.schemas(),club,"c_reputation",rep,"Club Reputation",edits);}
        ui.label("Facility value");ui.add(egui::Slider::new(&mut fac,1..=20));
        if ui.add_enabled(writable,egui::Button::new("APPLY ALL FACILITIES")).clicked(){for (label,key) in [("Training","c_training"),("Youth Facilities","c_youth_fac"),("Youth Improvement","c_youth_improve"),("Youth Coaching","c_youth_coach"),("Youth Recruitment","c_youth_recruit"),("Corporate","c_corporate")]{element_club_set_u8(club.build.schemas(),club,key,fac,label,edits);let mirror=format!("{key}_fin");element_club_set_u8(club.build.schemas(),club,&mirror,fac,&format!("{label} (finance mirror)"),edits);}}
    });
    ui.horizontal_wrapped(|ui|{
        ui.label("Balance £");ui.add(egui::DragValue::new(&mut bal).speed(1_000_000));
        ui.label("Transfer budget £");ui.add(egui::DragValue::new(&mut tb).speed(1_000_000));
        if ui.add_enabled(writable,egui::Button::new("APPLY FINANCE")).clicked(){element_club_set_u32(club.build.schemas(),club,"c_balance",bal,"Balance",edits);element_club_set_u32(club.build.schemas(),club,"c_transfer_budget",tb,"Transfer Budget",edits);element_club_set_u32(club.build.schemas(),club,"c_transfer_remaining",tb,"Transfer Remaining",edits);}
        if ui.add_enabled(writable,egui::Button::new("ZERO TRANSFER BUDGET")).clicked(){element_club_set_u32(club.build.schemas(),club,"c_transfer_budget",0,"Transfer Budget",edits);element_club_set_u32(club.build.schemas(),club,"c_transfer_remaining",0,"Transfer Remaining",edits);}
    });
    ui.ctx().data_mut(|d|{d.insert_temp(rep_id,rep);d.insert_temp(bal_id,bal);d.insert_temp(tb_id,tb);d.insert_temp(fac_id,fac);});
    ui.label(egui::RichText::new("FMRTE 27 also exposes Add/Remove/Duplicate Kit, Affiliates and ownership-related models. Those are true list/object operations, so Element does not emulate them with unsafe pointer writes until allocation/removal is certified.").small().weak());

    ui.add_space(12.0);
    ui.separator();
    ui.strong("Intentionally locked until independently mapped");
'''
    t=one(t,anchor,block,"club v8.2 write deck")

# Surface additional FMRTE-confirmed semantics in the real workspaces.
if "AddKitCommand / RemoveKitCommand / DuplicateKitCommand" not in t:
    t=t.replace('"FM27 kit/style types are identified in game metadata.",&["Home / Away / Third kits","Primary / secondary / trim colours","Shirt / shorts / socks","Pattern/style IDs"]', '"FMRTE 27 exposes AddKitCommand / RemoveKitCommand / DuplicateKitCommand and FM27 kit/style types are identified in game metadata.",&["Home / Away / Third kits","Primary / secondary / trim colours","Shirt / shorts / socks","Pattern/style IDs","Add / remove / duplicate kit record"]',1)
if "TransferProposals" not in t:
    t=t.replace('ui.horizontal_wrapped(|ui|{ui.heading("Transfer Center");ui.label(egui::RichText::new("ELEMENT v8.1 • MARKET WORKSPACE")', 'ui.horizontal_wrapped(|ui|{ui.heading("Transfer Center");ui.label(egui::RichText::new("ELEMENT v8.2 • MARKET + TRANSFER PROPOSAL LAB")',1)
    needle='let Some(cache)=cache else{return;};\n    ui.strong("Squad market");'
    if needle in t:
        t=t.replace(needle,'let Some(cache)=cache else{return;};\n    ui.label(egui::RichText::new("FMRTE 27 exposes TransferProposals. Element already has certified direct-settlement transfer ownership writes; native AI proposal creation is the next record-chain target, kept separate from direct Force Buy.").small().weak());\n    ui.strong("Squad market");',1)
wr(p,t)

print("Element v8.2 FULL WRITE ENGINE applied.")
