import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import play

class DisplayTests(unittest.TestCase):
    def test_connected_output_is_primary_without_mode_changes(self):
        report='eDP-1 connected 1600x1000+0+0\nHDMI-A-3 connected 1920x1080+1600+0\n'
        with patch.dict(os.environ,{'DISPLAY':':1'}),patch.object(play.shutil,'which',return_value='/usr/bin/xrandr'),patch.object(play.subprocess,'run',return_value=Mock(stdout=report)) as run:
            play.set_primary_monitor('HDMI-A-3')
            self.assertEqual(run.call_args_list[1].args[0],['xrandr','--output','HDMI-A-3','--primary'])

    def test_disconnected_or_option_like_output_cannot_change_display(self):
        for output in ['DP-1','--auto']:
            with patch.dict(os.environ,{'DISPLAY':':1'}),patch.object(play.shutil,'which',return_value='/usr/bin/xrandr'),patch.object(play.subprocess,'run',return_value=Mock(stdout='DP-1 disconnected\neDP-1 connected\n')) as run:
                with self.assertRaises(ValueError):play.set_primary_monitor(output)
                self.assertEqual(run.call_count,1)

    def test_check_never_applies_monitor_changes(self):
        with patch.object(sys,'argv',['arizona','--check','--monitor','HDMI-A-3']),patch.object(play.arizona,'check'),patch.object(play,'set_primary_monitor') as change:
            self.assertEqual(play.main(),0);change.assert_not_called()

if __name__=='__main__':unittest.main()
