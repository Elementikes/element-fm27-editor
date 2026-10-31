from pathlib import Path

path = Path.cwd() / "src" / "ui" / "player_panel.rs"
text = path.read_text(encoding="utf-8")

marker = "fn show_transfer_lab("
pos = text.find(marker)
if pos < 0:
    raise SystemExit("v5.0 boundary prep: show_transfer_lab not found")

# Inject the v5 market helpers directly before the Transfer Lab function.
# This intentionally avoids relying on historical comment separators, which
# changed across generated-source overlays.
helper = r'''fn element_v5_listing_now(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
) -> bool {
    let (Some(raw),Some(base),Some(today))=(player.contract_raw.as_mut(),player.contract_addr,player.game_date) else{return false;};
    let Some(date_off)=schemas.offset_of("p_list_date") else{return false;};
    let Some(flags_off)=schemas.offset_of("p_list_flags") else{return false;};
    let Some(code_off)=schemas.offset_of("p_list_code") else{return false;};
    if date_off+4>raw.len()||flags_off>=raw.len()||code_off>=raw.len(){return false;}
    let start=date_off;let end=code_off+1;
    if end>raw.len()||flags_off<start||flags_off>=end{return false;}
    let old=raw[start..end].to_vec();let mut new=old.clone();
    new[0..4].copy_from_slice(&today.raw.to_le_bytes());
    new[flags_off-start]=raw[flags_off]|1;
    new[code_off-start]=5;
    if new==old{return true;}
    raw[start..end].copy_from_slice(&new);
    edits.push(FieldEdit{addr:base+start as u64,old_raw:old,new_raw:new,description:"Sell Assist — transfer list now".into()});
    true
}

fn element_v5_offer_magnet(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
    percent: u32,
) {
    let _=element_v5_listing_now(schemas,player,edits);
    let Some(field)=schemas.field("p_value") else{return;};
    let Some(loc)=field.offset.as_ref() else{return;};
    let off=loc.offset() as usize;
    let Some(bytes)=player.raw.get(off..off+4) else{return;};
    let old=u32::from_le_bytes(bytes.try_into().unwrap());
    if old==0||old==u32::MAX{return;}
    let new=((u64::from(old)*u64::from(percent))/100).clamp(1,u64::from(u32::MAX)) as u32;
    if new==old{return;}
    player.raw[off..off+4].copy_from_slice(&new.to_le_bytes());
    edits.push(FieldEdit{addr:player.addr+off as u64,old_raw:old.to_le_bytes().to_vec(),new_raw:new.to_le_bytes().to_vec(),description:format!("Offer Magnet — transfer value {old} → {new} ({percent}%)")});
}

'''
if "fn element_v5_listing_now(" not in text:
    text = text[:pos] + helper + text[pos:]

path.write_text(text, encoding="utf-8")
print("v5.0 boundary prep completed: market helpers injected before show_transfer_lab.")
