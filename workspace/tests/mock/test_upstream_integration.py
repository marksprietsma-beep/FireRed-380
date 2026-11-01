"""Offline integration fixtures. No actual ROM/save files, emulator or model."""
import hashlib
import importlib
import io
import json
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace/src"))
from firered_bridge import mgba_client as adapter
from firered_bridge import safety
from firered_bridge.player import party, bag, pc, snapshot
from firered_bridge.ui import battle, fly_map
from firered_bridge.world.collision import process_tiles_to_collision_map
from firered_bridge.text.encoding import decode_gba_string
from firered_bridge.memory.symbols import sym_addr
from firered_bridge.state import builders
import owner_testing
import firered_mgba_bridge as api
from fastapi.testclient import TestClient


def load_battery():
    return safety.battery_module()


class AdapterTests(unittest.TestCase):
    def test_exact_hardened_transport_and_no_http_fallback(self):
        import bridge_client
        self.assertIsInstance(adapter._CLIENT, bridge_client.BridgeClient)
        source = Path(adapter.__file__).read_text()
        for forbidden in ('socket.create_connection', 'requests.get', 'requests.post', 'port_max'):
            self.assertNotIn(forbidden, source)

    def test_chunked_and_batched_readers(self):
        client = Mock()
        client.read_range_hex.side_effect = lambda addr, size: 'ab' * size
        with patch.object(adapter, '_authorized'), patch.object(adapter, '_CLIENT', client):
            self.assertEqual(adapter.mgba_read_range_bytes(0x02000000, 5000), b'\xab' * 5000)
            self.assertEqual(client.read_range_hex.call_count, 2)
            self.assertEqual(adapter.mgba_read_ranges([(1,2),(3,1)]), [[171,171],[171]])

    def test_no_input_replay_when_outcome_uncertain(self):
        from bridge_client import BridgeUncertainError
        client = Mock(); client.frame.return_value = 0; client.keys.return_value = 0
        client.hold_keys.side_effect = BridgeUncertainError('lost reply')
        with patch.object(safety, 'claim_action'), patch.object(adapter, '_CLIENT', client):
            with self.assertRaises(BridgeUncertainError): adapter.mgba_hold_button('A', 12)
        client.hold_keys.assert_called_once_with('A',12)
        client.clear_all.assert_called_once()

    def test_runtime_locked_without_manifest(self):
        with patch.object(safety, '_session', None), patch.dict(safety.os.environ, {}, clear=True):
            with self.assertRaises(PermissionError): adapter.mgba_read8(0)

    def test_action_budget_is_bounded(self):
        with patch.object(safety, 'require_authorized', return_value={}), patch.object(safety, '_paused', False), patch.object(safety, '_remaining', 1):
            safety.claim_action()
            with self.assertRaises(PermissionError): safety.claim_action()

    def test_file_adapter_cannot_escape_root(self):
        client = Mock(); client.call.return_value = str(ROOT)
        with patch.object(adapter, '_authorized'), patch.object(adapter, '_CLIENT', client):
            with self.assertRaises(ValueError): adapter.mgba_screenshot(str(ROOT.parent/'outside.png'))
            with self.assertRaises(ValueError): adapter.mgba_screenshot('original.sav')
        client.screenshot.assert_not_called()

    def test_reset_and_automatic_states_disabled(self):
        with self.assertRaises(PermissionError): adapter.mgba_reset()
        with patch.dict(adapter.os.environ, {}, clear=True):
            with self.assertRaises(PermissionError): adapter.mgba_save_state_file('test.mgbs')
        with patch.object(Path, 'mkdir') as mkdir:
            self.assertFalse(api._maybe_backup_savestate()['enabled'])
        mkdir.assert_not_called()


class ReaderFixtures(unittest.TestCase):
    def test_symbols_and_metadata_load_without_submodule(self):
        self.assertGreater(sym_addr('gPlayerParty'), 0)
        from firered_bridge.game_data import load_layout_id_table, load_reference_tables
        self.assertGreater(len(load_layout_id_table()), 300)
        self.assertEqual(load_reference_tables().species_names[25], 'PIKACHU')
        fly_map._load_map_sections(); fly_map._load_world_map_flag_ids(); fly_map._load_mapsec_to_world_map_flag_map()
        self.assertGreater(len(fly_map._MAPSECS), 100)
        self.assertGreater(len(fly_map._WORLD_MAP_FLAG_CONST_TO_ID), 10)
        self.assertIn('MAPSEC_PALLET_TOWN', fly_map._MAPSEC_TO_WORLD_MAP_FLAG_CONST)

    def test_party_pid_decryption_and_substructure_order(self):
        pid, otid = 17, 123
        raw = bytearray(48)
        index = party.SUBSTRUCTURE_ORDER[pid % 24].index('G')
        raw[index*12:index*12+2] = (25).to_bytes(2,'little')
        key = pid ^ otid
        encrypted = b''.join((int.from_bytes(raw[i:i+4],'little') ^ key).to_bytes(4,'little') for i in range(0,48,4))
        with patch.object(party.mgba,'mgba_read32',side_effect=[pid,otid]), patch.object(
                party.mgba,'mgba_read_range_bytes',return_value=encrypted):
            self.assertEqual(party.get_species_id_for_slot(0),25)

    def test_bag_quantity_decryption(self):
        key = 0xABCD
        raw = struct.pack('<HH',4,3 ^ key)
        entries = bag._read_pocket_items_from_raw(raw,1,key)
        self.assertEqual(entries[0]['id'],4)
        self.assertEqual(entries[0]['quantity'],3)

    def test_player_money_decryption(self):
        with patch.object(snapshot.mgba,'mgba_read32',side_effect=[0x02001000,500 ^ 123,0x02002000,123]):
            self.assertEqual(snapshot.get_player_money(),500)

    def test_pc_empty_slot_is_not_fabricated(self):
        self.assertIsNone(pc._parse_box_slot_to_party_schema(bytes(80)))

    def test_text_terminator_and_dialogue_prompt(self):
        self.assertEqual(decode_gba_string([0xBB,0xBC,0xFF,0xBD]),'AB')
        self.assertEqual(decode_gba_string([0xBB,0xFA,0xBC],stop_at_prompt=True),'A')

    def test_battle_hp_fields_and_inactive_state(self):
        raw = bytearray(100)
        raw[0:2] = (25).to_bytes(2,'little')
        raw[0x28:0x2a] = (12).to_bytes(2,'little'); raw[0x2a]=5
        raw[0x2c:0x2e] = (20).to_bytes(2,'little')
        state = battle._parse_battle_pokemon(bytes(raw))
        self.assertEqual(state['hp'],{'current':12,'max':20})
        self.assertEqual(state['level'],5)
        self.assertFalse(battle.get_battle_state(in_battle=False)['isActive'])

    def test_collision_bit_blocks_tile(self):
        result = process_tiles_to_collision_map([0,0x400],2,[0]*1024,0,False)
        self.assertNotEqual(result['minimap_data']['grid'][0][0], result['minimap_data']['grid'][0][1])

    def test_trace_builder_uses_real_interpretation(self):
        snap={'map_group':3,'map_num':0,'in_battle':False,'field_locked':False,
              'x':4,'y':7,'facing':'up','elevation':0,'surfing':False,'biking':False,'diving':False}
        with patch.object(builders.player_snapshot,'_read_player_snapshot',return_value=snap), patch.object(
                builders.ui_dialog,'get_dialog_state',return_value={'inDialog':True,'visibleText':'Hello'}), patch.object(
                builders.player_snapshot,'are_all_controls_locked',return_value=True):
            state=builders.build_input_trace_state()
        self.assertEqual(state['player']['position'],[4,7])
        self.assertTrue(state['dialog']['inDialog'])
        self.assertTrue(state['emulator']['allControlsLocked'])

    def test_start_menu_task_and_cursor_recognition(self):
        from firered_bridge.ui import menus
        with patch.object(menus,'_find_active_task_by_func',return_value=0):
            state=menus.get_start_menu_state(start_menu_window_id=0,start_menu_num_actions=2,
                      start_menu_cursor_pos=1,start_menu_actions_raw=[0,1])
        self.assertEqual(state['type'],'startMenu');self.assertEqual(state['selectedIndex'],1)
        self.assertTrue(state['options'][1]['selected'])

    def test_pokedex_callback_recognizes_loading_screen(self):
        from firered_bridge.ui import pokedex
        with patch.object(pokedex.mgba,'mgba_read32',return_value=0):
            state=pokedex.get_pokedex_state(pokedex.CB2_OPEN_POKEDEX_ADDR)
        self.assertEqual(state['screen'],'loading')
        self.assertIsNone(pokedex.get_pokedex_state(0))

    def test_fly_map_callback_and_prompt_recognition(self):
        with patch.object(fly_map,'_read_u32',return_value=0), patch.object(
                fly_map,'get_textprinter_text_for_window',return_value='FLY to where?'):
            state=fly_map.get_fly_map_state(callback2=fly_map.CB2_OPEN_FLY_MAP_ADDR)
        self.assertEqual(state['type'],'flyMap');self.assertFalse(state['isReady'])
        self.assertEqual(state['prompt'],'FLY to where?')

    def test_warp_event_coordinates_and_destination(self):
        from firered_bridge.world import events
        base=0x0203F000
        raw=struct.pack('<HHBBBB',4,7,0,1,2,3)
        with patch.dict(events._WARP_EVENTS_CACHE,{},clear=True), patch.object(events,'_get_map_events_base',return_value=base), patch.object(
                events.mgba,'mgba_read_ranges_bytes',return_value=[b'\x01',(0x0203F100).to_bytes(4,'little')]), patch.object(
                events.mgba,'mgba_read_range_bytes',return_value=raw):
            result=events.get_current_map_warp_events()
        self.assertEqual(result[0]['position'],[4,7]);self.assertEqual(result[0]['destMapGroup'],3)


class OwnerModeTests(unittest.TestCase):
    def manifest(self):
        return {'owner_authorized_save_modification':True,'rom_path':str(owner_testing.ROM_PATH),
                'active_save':str(owner_testing.SAVE_PATH),'active_rom_path_verified_in_mgba':True,
                'active_save_path_verified_in_mgba':True}

    def test_requires_explicit_opt_in_before_file_access(self):
        with patch.object(Path,'open') as opened:
            with self.assertRaises(PermissionError): owner_testing.verify_owner_rom(self.manifest())
        opened.assert_not_called()

    def test_wrong_rom_or_save_refused_without_reading(self):
        for field in ('rom_path','active_save'):
            value=self.manifest(); value[field]='C:/Emu/other.gba'
            with patch.object(owner_testing.sys,'platform','win32'), patch.object(Path,'open') as opened:
                with self.assertRaises(ValueError): owner_testing.verify_owner_rom(value,opt_in=True)
            opened.assert_not_called()

    def test_hash_mismatch_rejected_with_memory_fixture(self):
        with patch.object(owner_testing.sys,'platform','win32'), patch.object(Path,'is_symlink',return_value=False), patch.object(
                Path,'exists',return_value=False), patch.object(Path,'open',return_value=io.BytesIO(b'not a ROM')):
            with self.assertRaisesRegex(ValueError,'MD5/SHA-256'): owner_testing.verify_owner_rom(self.manifest(),opt_in=True)

    def test_both_hashes_and_waiver_results(self):
        md5=Mock();md5.hexdigest.return_value=owner_testing.ROM_MD5
        sha=Mock();sha.hexdigest.return_value=owner_testing.ROM_SHA256
        with patch.object(owner_testing.sys,'platform','win32'), patch.object(Path,'is_symlink',return_value=False), patch.object(
                Path,'exists',return_value=False), patch.object(Path,'open',return_value=io.BytesIO(b'approved fixture')), patch.object(
                owner_testing.hashlib,'md5',return_value=md5), patch.object(owner_testing.hashlib,'sha256',return_value=sha):
            result=owner_testing.verify_owner_rom(self.manifest(),opt_in=True)
        self.assertEqual(result['S1'],'OWNER-WAIVED');self.assertEqual(result['S2'],'OWNER-WAIVED')
        md5.update.assert_called_once();sha.update.assert_called_once()

    def test_battery_waived_checks_are_never_passed(self):
        b=load_battery(); c=Mock(host='127.0.0.1',port=8888,retries=0); c.version.return_value='wrong'
        report=b.run_checks(c,Path('/unused'),{},owner_authorized=True)
        self.assertFalse(report['all_pass'])
        waived=[r for r in report['results'] if r.get('status')=='OWNER-WAIVED']
        self.assertEqual({r['test'] for r in waived},{'S1','S2'})
        self.assertTrue(all(r['pass'] is None for r in waived))
        self.assertTrue(next(r for r in report['results'] if r['test']=='S3')['pass'])

    def test_surface_failure_blocks_inputs_even_in_owner_mode(self):
        b=load_battery(); c=Mock(host='127.0.0.1',port=8888,retries=0)
        with patch.object(b,'verify_read_only_surface',side_effect=ValueError('unsafe surface')):
            report=b.run_checks(c,Path('/unused'),{},owner_authorized=True)
        self.assertFalse(report['all_pass']);c.hold_keys.assert_not_called()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(api.app)

    def test_health_and_cached_minimap_offline(self):
        with patch.object(adapter._CLIENT,'read8') as read:
            response=self.client.get('/health')
            self.assertEqual(response.status_code,200)
            self.assertIn('session',response.json())
            self.assertTrue(self.client.get('/minimapSnapshot').json()['ok'])
        read.assert_not_called()

    def test_locked_api_cannot_act(self):
        with patch.object(safety,'_session',None), patch.dict(safety.os.environ,{},clear=True), patch.object(api,'_send_commands') as send:
            result=self.client.post('/sendCommands',json={'commands':['a']}).json()
        self.assertFalse(result['ok']);send.assert_not_called()

    def test_only_one_action_and_no_dialogue_macro(self):
        with patch.object(safety,'require_actions'), patch.object(safety,'pause'), patch.object(safety,'status',return_value={'authorized':False}), patch.object(api,'_send_commands') as send:
            for commands in [['a','b'],['a_until_end_of_dialog'],['  A_UNTIL_END_OF_DIALOG  '],[{'type':'hold','button':'A','frames':301}]]:
                self.assertFalse(self.client.post('/sendCommands',json={'commands':commands}).json()['ok'])
        send.assert_not_called()

    def test_requestdata_routes_full_state_and_screenshot(self):
        fixture={'player':{'position':[1,2],'movementMode':'WALK','strengthEnabled':False},'map':{},'party':[]}
        with patch.object(safety,'require_authorized',return_value={'output':Path('/fixture')}), patch.object(
                api,'build_full_state',return_value=fixture),patch.object(api,'mgba_screenshot',return_value={'ok':True}), patch.object(
                api,'_wait_for_file_ready',return_value=True):
            result=self.client.get('/requestData').json()
        self.assertTrue(result['ok']);self.assertEqual(result['data']['player']['position'],[1,2])
        self.assertFalse(result['data']['emulator']['saveStateBackup']['enabled'])

    def test_restart_is_explicitly_disabled(self):
        self.assertFalse(self.client.post('/restartConsole').json()['status'])
