import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
import unittest
import time
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QTextBrowser,QPushButton
from chat_backend import KimiSession
from chat_ui import ChatController
from pet import Pet

app=QApplication.instance() or QApplication([])

class SummaryTests(unittest.TestCase):
    def test_thought_chunks_accumulate_as_public_summary(self):
        events=[];s=KimiSession('.',emit=lambda k,v:events.append((k,v)))
        for text in ('核对需求','检查文件'):
            s.event({'method':'session/update','params':{'update':{'sessionUpdate':'agent_thought_chunk','content':{'type':'text','text':text}}}})
        self.assertEqual(events[-1],('summary_update','核对需求\n\n检查文件'))

    def test_tool_calls_become_progress_events(self):
        events=[];s=KimiSession('.',emit=lambda k,v:events.append((k,v)))
        s.event({'method':'session/update','params':{'update':{'sessionUpdate':'tool_call','title':'Bash: ls','status':'in_progress'}}})
        s.event({'method':'session/update','params':{'update':{'sessionUpdate':'tool_call_update','title':'Bash: ls','status':'completed'}}})
        self.assertEqual(events[0],('progress','正在执行：Bash: ls'))
        self.assertEqual(events[1],('progress','执行结束：Bash: ls'))

class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.pet=Pet();cls.pet.show()
        cls.c=ChatController(cls.pet,cls.temp.name);cls.pet.chat=cls.c
    @classmethod
    def tearDownClass(cls):
        cls.c.shutdown();cls.pet.close();cls.temp.cleanup()
    def test_summary_and_one_success_notification(self):
        c=self.c;p=self.pet
        c.active=c.store.new(self.temp.name);c.running_chat=c.active
        c.running_turn={'prompt':'测试','created':'now','status':'running','output':'','events':[]}
        c.active['turns'].append(c.running_turn)
        p.play(p.work_slots[1],'working')
        c.receive('summary_update','正在核对主人的需求。');c.preview_reply();c.render()
        self.assertIn('思考摘要（公开）',c.window.view.toPlainText())
        self.assertTrue(p.bubble.isVisible())
        self.assertTrue(p.bubble.is_task_progress)
        long='完整任务结果\n'*100
        result={'threadId':'test','text':long,'transcript':long}
        with patch.object(p,'play_click_sound') as sound:
            c.completed(result);c.completed(result)
            sound.assert_called_once()
        self.assertEqual(p.mode,'task-celebration');self.assertEqual(p.current['id'],'18')
        view=p.bubble.findChild(QTextBrowser);self.assertEqual(view.toPlainText(),long)
        app.processEvents();self.assertGreater(view.verticalScrollBar().maximum(),0)
        button=next(b for b in p.bubble.findChildren(QPushButton) if b.text()=='详情')
        button.click();self.assertTrue(c.window.isVisible())
        p.started=time.monotonic()-5;p.animate();self.assertEqual(p.mode,'idle')
    def test_failure_has_no_success_sound_or_animation(self):
        c=self.c;p=self.pet
        c.active=c.store.new(self.temp.name);c.running_chat=c.active
        c.running_turn={'prompt':'失败测试','created':'now','status':'running','output':'','events':[]}
        c.active['turns'].append(c.running_turn)
        with patch.object(p,'task_completed') as success,patch.object(p,'play_click_sound') as sound:
            c.failed('未完成',False);success.assert_not_called();sound.assert_not_called()
        self.assertEqual(p.mode,'work-failure');self.assertEqual(p.current['id'],'work06')

if __name__=='__main__':unittest.main()
