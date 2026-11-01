from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v8.1 missing {path}")
    return p.read_text(encoding='utf-8')

def wr(path,text): (root/path).write_text(text,encoding='utf-8')

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v8.1 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# App sidebar + swap result/dispatch + staff navigation.
# -----------------------------------------------------------------------------
p='src/app.rs'; t=rd(p)
# Player locked routes -> real tabs.
repls={
'                            locked(ui,"⇄  Comparison");':'                            pnav!("⇄  Comparison", player_panel::PlayerTab::Comparison);',
'                            locked(ui,"⚑  Career Plans");':'                            pnav!("⚑  Career Plans", player_panel::PlayerTab::CareerPlans);',
'                            locked(ui,"↔  Swap Player");':'                            pnav!("↔  Swap Player", player_panel::PlayerTab::SwapPlayer);',
'                            locked(ui,"▣  Clone Center");':'                            pnav!("▣  Clone Center", player_panel::PlayerTab::CloneCenter);',
'                            locked(ui,"▣  Work Permit");':'                            pnav!("▣  Work Permit", player_panel::PlayerTab::WorkPermit);',
'                            locked(ui,"☑  Promises");':'                            pnav!("☑  Promises", player_panel::PlayerTab::Promises);',
'                            locked(ui,"⌛  Retire Date");':'                            pnav!("⌛  Retire Date", player_panel::PlayerTab::Retirement);',
'                            pnav!("⌕  Scout Information", player_panel::PlayerTab::DataHub);':'                            pnav!("⌕  Scout Information", player_panel::PlayerTab::ScoutInfo);',
}
for a,b in repls.items():
    if a not in t: raise SystemExit(f'v8.1 app player sidebar marker missing: {a}')
    t=t.replace(a,b,1)
# Staff routes (same textual locked labels can appear player first; replace exact surrounding remaining occurrences).
for a,b in [
('                            locked(ui,"⚑  Career Plans");','                            snav!("⚑  Career Plans", staff_panel::StaffTab::CareerPlans);'),
('                            locked(ui,"☑  Promises");','                            snav!("☑  Promises", staff_panel::StaffTab::Promises);'),
('                            locked(ui,"↔  Swap Staff");','                            snav!("↔  Swap Staff", staff_panel::StaffTab::SwapStaff);'),
('                            locked(ui,"★  Training Rating");','                            snav!("★  Training Rating", staff_panel::StaffTab::TrainingRating);'),
('                            snav!("⌁  Formations / Tendencies", staff_panel::StaffTab::Overview);','                            snav!("⌁  Formations / Tendencies", staff_panel::StaffTab::Formations);'),
('                            locked(ui,"♟  Relationships");','                            snav!("♟  Relationships", staff_panel::StaffTab::Relationships);'),
('                            snav!("⌕  Knowledge", staff_panel::StaffTab::Overview);','                            snav!("⌕  Knowledge", staff_panel::StaffTab::Knowledge);'),
('                            locked(ui,"⌛  Retire Date");','                            snav!("⌛  Retire Date", staff_panel::StaffTab::Retirement);'),
('                            snav!("A  Languages", staff_panel::StaffTab::Overview);','                            snav!("A  Languages", staff_panel::StaffTab::Languages);'),
]:
    if a not in t: raise SystemExit(f'v8.1 app staff sidebar marker missing: {a}')
    t=t.replace(a,b,1)
# Club routes.
for a,b in [
('                            locked(ui,"◉  Club Vision");','                            cnav!("◉  Club Vision", club_panel::ClubTab::Vision);'),
('                            locked(ui,"＋  Possible Signings");','                            cnav!("＋  Possible Signings", club_panel::ClubTab::Recruitment);'),
('                            locked(ui,"§  Player Clauses");','                            cnav!("§  Player Clauses", club_panel::ClubTab::PlayerClauses);'),
('                            locked(ui,"⇄  Transfer Center");','                            cnav!("⇄  Transfer Center", club_panel::ClubTab::TransferCenter);'),
('                            locked(ui,"▱  Kits and Colours");','                            cnav!("▱  Kits and Colours", club_panel::ClubTab::Kits);'),
('                            locked(ui,"♟  Staff");','                            cnav!("♟  Staff", club_panel::ClubTab::Staff);'),
('                            locked(ui,"⌁  Affiliations");','                            cnav!("⌁  Affiliations", club_panel::ClubTab::Affiliations);'),
('                            locked(ui,"▰  Regional Divisions");','                            cnav!("▰  Regional Divisions", club_panel::ClubTab::RegionalDivisions);'),
('                            locked(ui,"▦  Ownership");','                            cnav!("▦  Ownership", club_panel::ClubTab::Ownership);'),
('                            locked(ui,"♟  Relationships");','                            cnav!("♟  Relationships", club_panel::ClubTab::Relationships);'),
]:
    if a not in t: raise SystemExit(f'v8.1 app club sidebar marker missing: {a}')
    t=t.replace(a,b,1)
# Swap results.
if 'BridgeResult::SwapPlayersOk' not in t:
    marker='                BridgeResult::ForceBuyOk(report) => {'; idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 app force result marker missing')
    arms=r'''                BridgeResult::SwapPlayersOk(report) => {
                    self.set_status(format!("Player Swap OK • 0x{:X} ↔ 0x{:X} • teams 0x{:X} ↔ 0x{:X}",report.player_a_addr,report.player_b_addr,report.team_a_before,report.team_b_before));
                    self.entity_cache=None;self.cache_load_state=CacheLoadState::Loading{done:0,total:0};self.bridge.send(BridgeCmd::LoadEntityCache);
                    if let Some(p)=self.selected_player.as_ref().filter(|p|p.addr==report.player_a_addr){self.bridge.send(BridgeCmd::LoadPlayer(p.addr,p.index));}
                }
                BridgeResult::SwapPlayersFail { player_addr:_, error } => self.set_status(format!("Player Swap aborted: {error}")),
'''
    t=t[:idx]+arms+t[idx:]
# Swap request dispatch.
if 'element_v81_swap_players_request' not in t:
    marker='        if let Some((player_addr,person_shift,contract_addr,target_club_addr,fee)) = ctx.data_mut(|d| {'; idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 app request marker missing')
    block=r'''        if let Some((player_a_addr,person_a_shift,contract_a_addr,player_b_addr,player_b_index)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v81_swap_players_request");
            let v=d.get_temp::<(u64,usize,u64,u64,usize)>(id);d.remove::<(u64,usize,u64,u64,usize)>(id);v
        }) {
            if self.conn.is_writable(){self.bridge.send(BridgeCmd::SwapPlayers{player_a_addr,person_a_shift,contract_a_addr,player_b_addr,player_b_index});self.set_status("Player Swap running • roster + contracts + transfer dates + read-back…".into());}
        }

'''
    t=t[:idx]+block+t[idx:]
# Staff navigation consume + open-contract post-nav.
if 'navigation::take_staff_target(ctx)' not in t:
    marker='        if nav_back_clicked {'; idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 navigation consume marker missing')
    block=r'''        if let Some(target) = navigation::take_staff_target(ctx) {
            let entry=HistoryEntry{entity_type:EntityTabType::Staff,addr:target.addr,index:target.index,display_name:target.name};
            self.push_history(entry.clone());self.activate_history_entry(entry);
        }
'''
    t=t[:idx]+block+t[idx:]
# After player navigation, consume contract flag.
old='''            self.push_history(entry.clone());\n            self.activate_history_entry(entry);\n        }\n        if let Some(target) = navigation::take_staff_target(ctx) {'''
new='''            self.push_history(entry.clone());\n            self.activate_history_entry(entry);\n            let open_contract=ctx.data_mut(|d|{let id=egui::Id::new("element_open_player_contract_after_nav");let v=d.get_temp::<bool>(id).unwrap_or(false);d.remove::<bool>(id);v});\n            if open_contract { self.player_tab=player_panel::PlayerTab::Contract; }\n        }\n        if let Some(target) = navigation::take_staff_target(ctx) {'''
if old not in t: raise SystemExit('v8.1 open contract navigation marker missing')
t=t.replace(old,new,1)
wr(p,t)


print("Element v8.1d app routing applied.")
