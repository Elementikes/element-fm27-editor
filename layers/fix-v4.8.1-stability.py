from pathlib import Path

root = Path.cwd()
path = root / "src" / "ui" / "club_logo.rs"
text = path.read_text(encoding="utf-8")

old_resolve = '''pub fn resolve(uid: u32, graphics_hint: Option<&str>) -> Option<PathBuf> {
    for root in graphics_roots(graphics_hint) {
        if let Some(path) = direct_candidates(&root, uid) { return Some(path); }
        if let Some(path) = search_pack(&root, uid) { return Some(path); }
    }
    None
}
'''
new_resolve = '''pub fn resolve(uid: u32, graphics_hint: Option<&str>) -> Option<PathBuf> {
    // STABILITY: never recursively crawl a graphics megapack from the egui
    // render thread. A missing crest used to scan up to ~80k entries every
    // frame, which could make an otherwise healthy click look like a crash.
    // Keep this path O(1)-ish: known direct filenames plus a handful of
    // top-level config.xml locations. A future async indexer can restore deep
    // pack discovery without blocking the UI.
    for root in graphics_roots(graphics_hint) {
        if let Some(path) = direct_candidates(&root, uid) { return Some(path); }
        for rel in [
            "config.xml",
            "logos/config.xml",
            "club_logos/config.xml",
            "logos/normal/config.xml",
            "logos/clubs/config.xml",
            "sortitoutsi/logos/config.xml",
        ] {
            let config = root.join(rel);
            if config.is_file() {
                if let Some(path) = config_match(&config, uid) { return Some(path); }
            }
        }
    }
    None
}
'''
if old_resolve not in text:
    raise SystemExit("v4.8.1 stability: resolve marker missing")
text = text.replace(old_resolve, new_resolve, 1)

old_render = '''pub fn render(ui: &mut egui::Ui, uid: u32, graphics_hint: Option<&str>, size: f32) -> bool {
    if uid == 0 { return false; }
    let texture_id = egui::Id::new(("element_club_crest_texture_v48", uid));
    if let Some(texture) = ui.ctx().data_mut(|data| data.get_temp::<egui::TextureHandle>(texture_id)) {
        ui.add(egui::Image::new(&texture).fit_to_exact_size(egui::vec2(size, size)));
        return true;
    }
    let Some(path) = resolve(uid, graphics_hint) else { return false; };
    let Ok(bytes) = std::fs::read(&path) else { return false; };
    let Ok(decoded) = image::load_from_memory(&bytes) else { return false; };
    let rgba = decoded.to_rgba8();
    let image = egui::ColorImage::from_rgba_unmultiplied([rgba.width() as usize, rgba.height() as usize], rgba.as_raw());
    let texture = ui.ctx().load_texture(format!("element_club_crest_v48_{uid}"), image, egui::TextureOptions::LINEAR);
    ui.ctx().data_mut(|data| data.insert_temp(texture_id, texture.clone()));
    ui.add(egui::Image::new(&texture).fit_to_exact_size(egui::vec2(size, size)))
        .on_hover_text(format!("Club crest • UID {uid}\\n{}", path.display()));
    true
}
'''
new_render = '''pub fn render(ui: &mut egui::Ui, uid: u32, graphics_hint: Option<&str>, size: f32) -> bool {
    if uid == 0 { return false; }
    let hint_key = graphics_hint.unwrap_or("").to_owned();
    let texture_id = egui::Id::new(("element_club_crest_texture_v481", uid, hint_key.clone()));
    let miss_id = egui::Id::new(("element_club_crest_missing_v481", uid, hint_key));
    if let Some(texture) = ui.ctx().data_mut(|data| data.get_temp::<egui::TextureHandle>(texture_id)) {
        ui.add(egui::Image::new(&texture).fit_to_exact_size(egui::vec2(size, size)));
        return true;
    }
    if ui.ctx().data_mut(|data| data.get_temp::<bool>(miss_id).unwrap_or(false)) {
        return false;
    }
    let Some(path) = resolve(uid, graphics_hint) else {
        ui.ctx().data_mut(|data| data.insert_temp(miss_id, true));
        return false;
    };
    let Ok(bytes) = std::fs::read(&path) else {
        ui.ctx().data_mut(|data| data.insert_temp(miss_id, true));
        return false;
    };
    let Ok(decoded) = image::load_from_memory(&bytes) else {
        ui.ctx().data_mut(|data| data.insert_temp(miss_id, true));
        return false;
    };
    let rgba = decoded.to_rgba8();
    let image = egui::ColorImage::from_rgba_unmultiplied([rgba.width() as usize, rgba.height() as usize], rgba.as_raw());
    let texture = ui.ctx().load_texture(format!("element_club_crest_v481_{uid}"), image, egui::TextureOptions::LINEAR);
    ui.ctx().data_mut(|data| data.insert_temp(texture_id, texture.clone()));
    ui.add(egui::Image::new(&texture).fit_to_exact_size(egui::vec2(size, size)))
        .on_hover_text(format!("Club crest • UID {uid}\\n{}", path.display()));
    true
}
'''
if old_render not in text:
    raise SystemExit("v4.8.1 stability: render marker missing")
text = text.replace(old_render, new_render, 1)
path.write_text(text, encoding="utf-8")
print("Element v4.8.1 stability hotfix applied: non-blocking crest lookup path + negative cache.")
