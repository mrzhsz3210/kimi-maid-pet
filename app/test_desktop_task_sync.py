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
        for name in ('task_started','task_finished','task_failed','task_progress','task_completed','task_result','say'):
            setattr(self,name,Mock())

def write_state(root, workspace, session, **fields):
    folder=Path(root)/workspace/session
    folder.mkdir(parents=True,exist_ok=True)
    data={'id':session,'archived':False,'updatedAt':int(time.time()*1000),**fields}
    (folder/'state.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    return data

class WatcherSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.now=[time.time()]
        self.pet=FakePet()
        self.sync=DesktopTaskSync(self.pet,sessions_root=self.tmp.name,clock=lambda:self.now[0])
    def tearDown(self):
        self.tmp.cleanup()
    def test_running_then_completed(self):
        write_state(self.tmp.name,'w','s1',title='修问题',lastTurnReason=None,lastPrompt='帮我修问题')
        self.sync.poll()
        self.pet.task_started.assert_called_once()
        self.assertIn('收到',self.pet.task_progress.call_args.args[0])
        write_state(self.tmp.name,'w','s1',title='修问题',lastTurnReason='completed')
        self.sync.poll()
        self.pet.task_finished.assert_called_once()
        self.pet.task_completed.assert_called_once()
        self.assertIn('修问题',self.pet.task_completed.call_args.args[0])
    def test_failure_never_celebrates(self):
        write_state(self.tmp.name,'w','s1',title='任务',lastTurnReason=None)
        self.sync.poll()
        write_state(self.tmp.name,'w','s1',title='任务',lastTurnReason='error')
        self.sync.poll()
        self.pet.task_completed.assert_not_called()
        self.pet.task_failed.assert_called_once()
        self.assertIn('还没有完成',self.pet.task_progress.call_args.args[0])
    def test_old_sessions_are_ignored(self):
        write_state(self.tmp.name,'w','old',title='旧任务',lastTurnReason=None,
                    updatedAt=int((self.now[0]-3600)*1000))
        self.sync.poll()
        self.pet.task_started.assert_not_called()
    def test_fast_turn_reports_completion_once(self):
        write_state(self.tmp.name,'w','s1',title='秒完任务',lastTurnReason='completed')
        self.sync.poll();self.sync.poll()
        self.pet.task_completed.assert_called_once()
    def test_parallel_sessions_block_finish_until_all_done(self):
        write_state(self.tmp.name,'w','a',title='A',lastTurnReason=None)
        write_state(self.tmp.name,'w','b',title='B',lastTurnReason=None)
        self.sync.poll()
        write_state(self.tmp.name,'w','a',title='A',lastTurnReason='completed')
        self.sync.poll()
        self.pet.task_finished.assert_not_called()
        write_state(self.tmp.name,'w','b',title='B',lastTurnReason='completed')
        self.sync.poll()
        self.pet.task_finished.assert_called_once()
    def test_archived_session_finishes_quietly(self):
        write_state(self.tmp.name,'w','s1',title='任务',lastTurnReason=None)
        self.sync.poll()
        self.pet.task_started.assert_called_once()
        write_state(self.tmp.name,'w','s1',title='任务',archived=True)
        self.sync.poll()
        self.pet.task_finished.assert_called_once()
        self.pet.task_completed.assert_not_called()
        self.pet.task_failed.assert_not_called()
        self.assertNotIn('s1',self.sync.running)
        self.assertNotIn('s1',self.sync.known)
    def test_cancelled_is_not_failure(self):
        write_state(self.tmp.name,'w','s1',title='任务',lastTurnReason=None)
        self.sync.poll()
        write_state(self.tmp.name,'w','s1',title='任务',lastTurnReason='cancelled')
        self.sync.poll()
        self.pet.task_finished.assert_called_once()
        self.pet.task_completed.assert_not_called()
        self.pet.task_failed.assert_not_called()
        self.assertIn('已停下',self.pet.task_progress.call_args.args[0])
    def test_pet_own_sessions_excluded(self):
        own=write_state(self.tmp.name,'w','own-session',title='桌宠自己的任务',lastTurnReason=None)
        self.sync.excluded=lambda:{'own-session'}
        self.sync.poll()
        self.pet.task_started.assert_not_called()
    def test_silent_task_reminder_after_five_minutes(self):
        data=write_state(self.tmp.name,'w','s1',title='长任务',lastTurnReason=None)
        self.sync.poll()
        self.pet.task_progress.reset_mock()
        # 文件不再更新（mtime 不变），但任务超过 5 分钟没有动静
        self.now[0]+=299;self.sync.poll();self.pet.task_progress.assert_not_called()
        self.now[0]+=2;self.sync.poll();self.pet.task_progress.assert_called_once()

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
