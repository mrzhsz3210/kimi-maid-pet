import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from chat_backend import HistoryStore, KimiSession, TaskCancelled, persona_text


class BackendTests(unittest.TestCase):
    def test_custom_pet_name_updates_default_persona(self):
        with tempfile.TemporaryDirectory() as folder, patch('chat_backend.data_directory',return_value=Path(folder)):
            text=persona_text('没药')
            self.assertIn('你是「没药」',text)
            self.assertNotIn('你是「Kimi娘」',text)

    def test_persistence_and_unfinished_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            store=HistoryStore(folder);chat=store.new(folder)
            chat['threadId']='persisted-thread'
            chat['turns'].append({'status':'running','prompt':'hello'})
            store.save();reloaded=HistoryStore(folder)
            self.assertEqual(reloaded.conversations[0]['threadId'],'persisted-thread')
            self.assertEqual(reloaded.conversations[0]['turns'][0]['status'],'interrupted')

    def test_corrupt_history_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'conversations.json';path.write_text('broken')
            with self.assertRaises(RuntimeError):HistoryStore(folder)
            self.assertEqual(path.read_text(),'broken')

    def test_output_assembly_accumulates_chunks(self):
        s=KimiSession('.')
        s.thread_id='t'
        s.event({'method':'session/update','params':{'sessionId':'other','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'wrong'}}}})
        for text in ('Checking…','Done'):
            s.event({'method':'session/update','params':{'sessionId':'t','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':text}}}})
        self.assertEqual(s.final_text(),'Checking…Done')
        self.assertEqual(s.transcript(),'Checking…Done')

    def test_replayed_history_is_ignored_during_load(self):
        s=KimiSession('.')
        s.thread_id='t';s.loading=True
        s.event({'method':'session/update','params':{'sessionId':'t','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'old'}}}})
        self.assertEqual(s.transcript(),'')

    def test_missing_interaction_handler_never_auto_approves(self):
        s=KimiSession('.')
        with patch.object(s,'send') as send:
            s.answer_request({'id':12,'method':'unknown/tool','params':{}})
            self.assertIn('error',send.call_args.args[0])

    def test_chat_mode_auto_cancels_permission(self):
        s=KimiSession('.',mode='chat')
        with patch.object(s,'send') as send:
            s.answer_request({'id':7,'method':'session/request_permission','params':{'options':[{'optionId':'allow','kind':'allow_once'}]}})
            response=send.call_args.args[0]
            self.assertEqual(response['result'],{'outcome':{'outcome':'cancelled'}})

    def test_voice_chat_allows_only_public_web_tools(self):
        s=KimiSession('.',mode='chat',allow_web=True)
        web={'toolCall':{'title':'WebSearch'},'options':[{'optionId':'allow','kind':'allow_once'}]}
        with patch.object(s,'send') as send:
            s.answer_request({'id':8,'method':'session/request_permission','params':web})
            response=send.call_args.args[0]
            self.assertEqual(response['result']['outcome']['outcome'],'selected')
        command={'toolCall':{'title':'Bash'},'options':[{'optionId':'allow','kind':'allow_once'}]}
        with patch.object(s,'send') as send:
            s.answer_request({'id':9,'method':'session/request_permission','params':command})
            response=send.call_args.args[0]
            self.assertEqual(response['result'],{'outcome':{'outcome':'cancelled'}})

    def test_cancellation_interrupts_current_turn(self):
        s=KimiSession('.',thread_id='t');s.cancel.set()
        with patch.object(s,'send') as send:
            with self.assertRaises(TaskCancelled):s.next(10**20)
            self.assertEqual(send.call_args.args[0]['method'],'session/cancel')

    def test_resume_uses_session_load(self):
        from types import SimpleNamespace
        s=KimiSession('.',thread_id='saved-thread')
        calls=[]
        def rpc(method,params,timeout=60):
            calls.append((method,params))
            if method=='session/load':return {}
            return {}
        def send(value):
            if value.get('method')=='session/prompt':s._prompt_id=value['id']
        def next_(deadline):
            if not getattr(s,'_fed',False):
                s._fed=True
                return {'method':'session/update','params':{'sessionId':'saved-thread','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'Okay'}}}}
            return {'id':s._prompt_id,'result':{'stopReason':'end_turn'}}
        with patch.object(s,'start',lambda:setattr(s,'process',SimpleNamespace(poll=lambda:None))),\
             patch.object(s,'close'),patch.object(s,'rpc',side_effect=rpc),\
             patch.object(s,'send',side_effect=send),patch.object(s,'next',side_effect=next_):
            self.assertEqual(s.run('continue')['text'],'Okay')
        self.assertEqual(calls[1][0],'session/load')
        self.assertEqual(calls[1][1]['sessionId'],'saved-thread')


from PySide6.QtWidgets import QApplication,QLabel,QPushButton
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest
from pet import Pet
from chat_ui import ChatController,TaskWorker

app=QApplication.instance() or QApplication([])


class ChatUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.pet=Pet();cls.pet.show()
        cls.controller=ChatController(cls.pet,cls.temp.name);cls.pet.chat=cls.controller

    @classmethod
    def tearDownClass(cls):
        cls.controller.shutdown();cls.pet.tick.stop();cls.pet.bubble.hide();cls.pet.hide()
        cls.temp.cleanup()

    def tearDown(self):
        self.controller.hide();self.controller.window.hide();self.pet.bubble.hide()

    def test_menu_submenus_and_idle_preview(self):
        menu=self.pet.context_menu();actions={a.text():a for a in menu.actions()}
        self.assertEqual(len(actions['互动差分动画'].menu().actions()),17)
        self.assertEqual(len(actions['工作差分动画'].menu().actions()),6)
        self.assertTrue(actions['工作差分动画'].menu().actions()[0].isEnabled())
        idle=actions['待机差分动画'].menu().actions()
        self.assertEqual(idle[1].text(),'待机动作02');idle[1].trigger()
        self.assertEqual(self.pet.current,self.pet.idles[1]);menu.deleteLater()

    def test_composer_stays_below_pet_at_screen_edges(self):
        c=self.controller;c.toggle()
        self.pet.move(self.pet.constrained_position(QPoint(99999,99999)))
        app.processEvents();c.position()
        area=app.primaryScreen().availableGeometry()
        self.assertEqual(c.composer.y(),self.pet.y()+self.pet.height()+8)
        self.assertTrue(area.contains(c.composer.frameGeometry()))
        c.composer.close();self.assertFalse(c.enabled)

    def test_long_result_details_and_full_history(self):
        c=self.controller;chat=c.store.new(self.temp.name)
        text='完整结果，不能丢失。\n'*80
        turn={'prompt':'test','created':'now','status':'running','output':'','events':[]}
        chat['turns'].append(turn);c.active=chat;c.running_chat=chat;c.running_turn=turn
        c.completed({'threadId':'x','text':text,'transcript':text})
        app.processEvents()
        labels=self.pet.bubble.findChildren(QLabel)
        self.assertEqual(labels[0].text(),'主人，完成啦！')
        buttons=[b for b in self.pet.bubble.findChildren(QPushButton) if b.text()=='详情']
        self.assertEqual(len(buttons),1);buttons[0].click()
        self.assertTrue(c.window.isVisible());self.assertIn(text.strip(),c.window.view.toPlainText())
        self.assertEqual(HistoryStore(self.temp.name).conversations[-1]['turns'][-1]['result'],text)

    def test_failure_does_not_claim_success(self):
        c=self.controller;chat=c.store.new(self.temp.name)
        turn={'prompt':'test','created':'now','status':'running','output':'','events':[]}
        chat['turns'].append(turn);c.active=chat;c.running_chat=chat;c.running_turn=turn
        c.failed('模拟连接中断',False)
        self.assertEqual(turn['status'],'failed')
        self.assertNotIn('任务完成啦',self.pet.bubble.findChildren(QLabel)[0].text())

    def test_close_history_keeps_pet_and_draft(self):
        c=self.controller;c.open_history();c.window.editor.setPlainText('未发送的草稿')
        c.window.close();app.processEvents()
        self.assertFalse(c.window.isVisible());self.assertTrue(self.pet.isVisible())
        self.assertEqual(c.window.editor.toPlainText(),'未发送的草稿')

    def test_voice_prompt_does_not_open_composer(self):
        self.controller.hide()
        with patch.object(self.controller,'submit') as submit:
            self.pet.submit_voice_prompt('这是她听见的话')
            submit.assert_called_once_with('这是她听见的话',mode='chat',source='voice')
            self.assertFalse(self.controller.composer.isVisible())
            self.assertIn('她听见的话',self.pet.bubble.findChildren(QLabel)[0].text())

    def test_voice_prompt_uses_separate_read_only_chat(self):
        c=self.controller;c.active=c.store.new(self.temp.name,mode='work')
        voice=Mock();self.pet.voice=voice
        with patch('quota.find_kimi',return_value='kimi'),patch('chat_ui.KimiSession.run',return_value={'threadId':'voice-thread','text':'语音答复','transcript':'语音答复'}):
            c.submit('语音问题',mode='chat',source='voice')
            self.assertEqual(c.active['mode'],'chat')
            self.assertEqual(c.worker.mode,'chat')
            self.assertTrue(c.worker.allow_web)
            with patch.object(self.pet,'task_progress') as progress:
                c.receive('output','不该弹出的流式摘要');c.preview_reply()
                progress.assert_not_called()
            for _ in range(30):
                QTest.qWait(30)
                if not c.busy:break
            self.assertFalse(c.busy)
            self.assertEqual(c.active['turns'][-1]['prompt'],'语音问题')
            self.assertEqual(self.pet.bubble.findChildren(QLabel)[0].text(),self.pet.pet_name+' · 回答')
            voice.begin_followup.assert_called_once()
        self.pet.voice=None

    def test_async_worker_does_not_block_and_preserves_thread(self):
        c=self.controller;c.active=c.store.new(self.temp.name)
        with patch('quota.find_kimi',return_value='kimi'),patch('chat_ui.KimiSession.run',return_value={'threadId':'returned','text':'答复','transcript':'答复'}):
            c.submit('测试后台')
            self.assertTrue(c.busy)
            for _ in range(30):
                QTest.qWait(30)
                if not c.busy:break
            self.assertFalse(c.busy)
            self.assertEqual(c.active['threadId'],'returned')
            self.assertEqual(c.active['turns'][-1]['status'],'completed')


if __name__=='__main__':unittest.main()
