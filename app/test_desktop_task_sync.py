import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json, tempfile, time, unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication
from desktop_task_sync import DesktopTaskSync

app=QApplication.instance() or QApplication([])

class FakePet(QObject):
    def __init__(self):
        super().__init__()
        self.chat=None
        self.settings=Mock();self.settings.value.return_value=True
        for name in ('task_started','task_finished','task_progress','task_completed','task_result','say'):
            setattr(self,name,Mock())

def write_events(path,events):
    with path.open('a',encoding='utf-8') as handle:
        for event in events:handle.write(json.dumps(event,ensure_ascii=False)+'\n')

class HookSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'sync-events.jsonl'
        self.now=[1000.0]
        self.pet=FakePet()
        self.sync=DesktopTaskSync(self.pet,log_path=self.path,clock=lambda:self.now[0])
    def tearDown(self):
        self.tmp.cleanup()
    def test_start_progress_stop_flow(self):
        self.sync.start()
        write_events(self.path,[
            {'hook_event_name':'TurnStarted','session_id':'s1','session_title':'修问题','prompt':'帮我修问题','turn_id':'t1'},
            {'hook_event_name':'PostToolUse','session_id':'s1','tool_name':'Bash'}])
        self.sync.poll()
        self.pet.task_started.assert_called_once()
        texts=[c.args[1] for c in self.pet.task_progress.call_args_list]
        self.assertTrue(any('帮你处理' in t for t in texts))
        self.assertTrue(any('Bash' in t for t in texts))
        write_events(self.path,[{'hook_event_name':'Stop','session_id':'s1'}])
        self.sync.poll()
        self.pet.task_finished.assert_called_once()
        self.pet.task_completed.assert_called_once()
    def test_old_events_are_skipped_on_start(self):
        write_events(self.path,[{'hook_event_name':'TurnStarted','session_id':'old','session_title':'旧任务'}])
        self.sync.start();self.sync.poll()
        self.pet.task_started.assert_not_called()
    def test_failure_never_celebrates(self):
        self.sync.start()
        write_events(self.path,[
            {'hook_event_name':'TurnStarted','session_id':'s1'},
            {'hook_event_name':'StopFailure','session_id':'s1'}])
        self.sync.poll()
        self.pet.task_completed.assert_not_called()
        self.assertIn('还没有完成',self.pet.task_progress.call_args.args[0])
    def test_interrupt_reports_interruption(self):
        self.sync.start()
        write_events(self.path,[
            {'hook_event_name':'TurnStarted','session_id':'s1'},
            {'hook_event_name':'Interrupt','session_id':'s1'}])
        self.sync.poll()
        self.pet.task_completed.assert_not_called()
        self.assertIn('中断',self.pet.task_progress.call_args.args[0])
    def test_parallel_sessions_block_finish_until_all_done(self):
        self.sync.start()
        write_events(self.path,[
            {'hook_event_name':'TurnStarted','session_id':'a'},
            {'hook_event_name':'TurnStarted','session_id':'b'},
            {'hook_event_name':'Stop','session_id':'a'}])
        self.sync.poll()
        self.pet.task_finished.assert_not_called()
        self.pet.task_completed.assert_called_once()
        write_events(self.path,[{'hook_event_name':'Stop','session_id':'b'}])
        self.sync.poll()
        self.pet.task_finished.assert_called_once()
    def test_silent_task_reminder_after_five_minutes(self):
        self.sync.start()
        write_events(self.path,[{'hook_event_name':'TurnStarted','session_id':'s1'}])
        self.sync.poll()
        self.pet.task_progress.reset_mock()
        self.now[0]+=299;self.sync.poll();self.pet.task_progress.assert_not_called()
        self.now[0]+=2;self.sync.poll();self.pet.task_progress.assert_called_once()
    def test_permission_request_alerts(self):
        self.sync.start()
        write_events(self.path,[
            {'hook_event_name':'TurnStarted','session_id':'s1'},
            {'hook_event_name':'PermissionRequest','session_id':'s1','tool_name':'Bash'}])
        self.sync.poll()
        self.assertIn('确认权限',self.pet.task_progress.call_args.args[1])
    def test_stop_without_start_is_ignored(self):
        self.sync.start()
        write_events(self.path,[{'hook_event_name':'Stop','session_id':'nobody'}])
        self.sync.poll()
        self.pet.task_completed.assert_not_called()
        self.pet.task_finished.assert_not_called()

class DockIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pet import Pet
        cls.pet=Pet();cls.pet.tick.stop()
    @classmethod
    def tearDownClass(cls):cls.pet.close()
    def test_docked_start_progress_completion_failure_only_bubbles(self):
        p=self.pet;p.dock_edge='left';p.play(p.idles[0],'idle')
        with patch.object(p,'play_click_sound'):
            p.task_started();p.task_progress('主人，我收到啦！','任务已收到',lambda:None)
            self.assertEqual(p.mode,'idle');self.assertEqual(p.dock_edge,'left');self.assertTrue(p.bubble.isVisible())
            p.task_progress('主人，遇到一个问题。','请确认权限',lambda:None);self.assertEqual(p.mode,'idle')
            p.task_finished();p.task_completed('完整任务结果',lambda:None)
            self.assertEqual(p.mode,'idle');self.assertEqual(p.dock_edge,'left');self.assertEqual(p.bubble.result_view.toPlainText(),'完整任务结果')
        p.undock()
    def test_can_dock_during_active_task(self):
        p=self.pet;area=QApplication.primaryScreen().availableGeometry()
        p.task_started();p.move(area.left(),area.top()+100)
        self.assertTrue(p.try_dock());self.assertEqual(p.dock_edge,'left')
        self.assertTrue(p.task_active);self.assertEqual(p.mode,'idle')
        p.task_progress('进展','正在处理',lambda:None);self.assertTrue(p.bubble.isVisible())
        p.undock();p.task_finished()
    def test_docked_bubble_is_close_and_can_be_dismissed(self):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QRegion
        p=self.pet;area=QApplication.primaryScreen().availableGeometry()
        for side in ('left','right'):
            p.move(area.left() if side=='left' else area.right()+1-p.width(),area.center().y()-p.height()//2)
            p.dock_edge=side;p.dock_started=time.monotonic()-1
            p.task_progress('主人，进度来了。','测试进展',lambda:None)
            pixmap=p.grab();b=QRegion(pixmap.mask()).boundingRect();r=pixmap.devicePixelRatio()
            visible=QRectF(b.x()/r,b.y()/r,b.width()/r,b.height()/r).toAlignedRect().translated(p.pos())
            gap=p.bubble.x()-visible.right()-1 if side=='left' else visible.left()-p.bubble.frameGeometry().right()-1
            self.assertGreaterEqual(gap,0);self.assertLessEqual(gap,8)
            self.assertTrue(p.bubble.close_button.isVisible())
            p.task_active=True;p.bubble.close_button.click()
            self.assertFalse(p.bubble.isVisible());self.assertFalse(p.bubble_timer.isActive());self.assertTrue(p.task_active)
            p.task_active=False;p.undock()
    def test_pose_changes_select_the_right_animation_policy(self):
        p=self.pet;area=QApplication.primaryScreen().availableGeometry();p.task_started()
        p.move(area.left(),area.top()+100);self.assertTrue(p.try_dock())
        with patch('pet.random.choices',return_value=[p.idles[0]]) as choice:
            p.idle();self.assertEqual(choice.call_args.kwargs['weights'],[7,3])
        p.begin_undock();start=p.dock_exit[0];work=p.regular_work_animations()
        with patch('pet.time.monotonic',return_value=start+.31),patch('pet.random.choices',return_value=[('working',work)]),patch('pet.random.choice',return_value=work[0]):p.animate()
        self.assertIsNone(p.dock_edge);self.assertEqual(p.mode,'working')
        p.move(area.left(),area.top()+100);self.assertTrue(p.try_dock());p.task_finished()
        with patch.object(p,'play_click_sound'):p.task_completed('完成',lambda:None)
        self.assertEqual(p.mode,'idle');self.assertEqual(p.dock_edge,'left')
        p.begin_undock();start=p.dock_exit[0]
        with patch('pet.time.monotonic',return_value=start+.31):p.animate()
        self.assertIsNone(p.dock_edge);self.assertEqual(p.mode,'idle');self.assertFalse(p.task_active)

if __name__=='__main__':unittest.main()
