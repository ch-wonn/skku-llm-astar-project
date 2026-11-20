"""Offline checks. No real API requests or credentials are used."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import openai
from llmastar.utils.waypoints import parse_waypoints, WaypointParseError
from llmastar.model.chatgpt import ChatGPT, IncompleteLLMResponse
from reproduction_support import validate_path
import run_reproduction as runner
import summarize_reproduction as summary


class ReproductionTests(unittest.TestCase):
    def test_parser(self):
        self.assertEqual(parse_waypoints('Explanation\nGenerated Path: [\n[2, 2], [5, 7], [9, 9]\n]'),[[2,2],[5,7],[9,9]])
        self.assertEqual(parse_waypoints('Generated Path: [[2,2],[9,9]]'),[[2,2],[9,9]])
        self.assertEqual(parse_waypoints('[[2,2],[10 - 0.5,9]]'),[[2,2],[9.5,9]])
        for text in ['Explanation only','Generated Path: [[2,2],','[[1,2,3],[4,5]]','[[True,2],[3,4]]']:
            with self.assertRaises(WaypointParseError):
                parse_waypoints(text)

    def test_adapter(self):
        response={'model':'mock','choices':[{'finish_reason':'length','message':{'content':'truncated'}}]}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-test','LLM_MAX_OUTPUT_TOKENS':'1000'}):
            with patch.object(openai.ChatCompletion,'create',return_value=response) as call:
                model=ChatGPT('test','',None)
                with self.assertRaises(IncompleteLLMResponse):
                    model.ask('test',max_tokens=1000)
                self.assertIsNone(call.call_args.kwargs['stop'])
                self.assertEqual(model.last_call['finish_reason'],'length')

    def test_validator_and_statistics(self):
        q={'start':[2,2],'goal':[9,9],'range_x':[0,12],'range_y':[0,12],
           'horizontal_barriers':[],'vertical_barriers':[]}
        self.assertFalse(validate_path([[2,2],[9,9]],q,{'length':1})[0])
        path=[[i,i] for i in range(2,10)]
        self.assertTrue(validate_path(path[::-1],q,{'length':7*2**.5})[0])
        ci=summary.cluster_estimate([0,0,1,1],[np.log(.5)]*4,[1]*4,np.array([[0,0],[0,1],[1,1]]),True)
        np.testing.assert_allclose(ci,[50,50])

    def test_end_to_end_resume_and_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            data=[]
            for i in range(3):
                data.append({'id':i,'range_x':[0,12],'range_y':[0,12],
                             'horizontal_barriers':[],'vertical_barriers':[[6,1,5]],
                             'start_goal':[[[2,2],[9,9]],[[2,3],[8,8]]]})
            dataset=root/'dataset.json';dataset.write_text(json.dumps(data))
            calls=[]
            def fake(**kw):
                calls.append(kw)
                text=kw['messages'][0]['content']
                start=json.loads(re.findall(r'Start Point: (\[[^\n]+)',text)[-1])
                goal=json.loads(re.findall(r'Goal Point: (\[[^\n]+)',text)[-1])
                return {'model':'mock','usage':{'prompt_tokens':600,'completion_tokens':70},
                    'choices':[{'finish_reason':'stop','message':{'content':'Explanation\nGenerated Path: '+json.dumps([start,[5,7],goal])}}]}
            def run(method,prompt,out,limit=None):
                argv=['run_reproduction.py','--method',method,'--prompt',prompt,'--dataset',str(dataset),'--out',str(out),'--plots','0']
                if limit: argv+=['--limit',str(limit)]
                with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
                    runner.main()
            with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-test','OPENAI_MODEL':'gpt-4o-mini'}):
                with patch.object(openai.ChatCompletion,'create',side_effect=fake):
                    run('astar','standard',root/'astar')
                    for prompt in ['standard','cot','repe']:
                        run('llm',prompt,root/prompt,2)
                        run('llm',prompt,root/prompt)
                        run('llm',prompt,root/prompt)
                        rows=[json.loads(p.read_text()) for p in (root/prompt/'cases').glob('*.json')]
                        self.assertEqual(len(rows),6)
                        self.assertTrue(all(r['status']=='valid' for r in rows))
                        self.assertTrue(all(r['waypoint_audit']['intermediate_count']==1 for r in rows))
                        self.assertTrue(all(r['waypoint_audit']['target_transitions'] for r in rows))
                    self.assertEqual(len(calls),18)
                with patch.object(sys,'argv',['summarize_reproduction.py','--root',str(root),'--bootstrap','1000']),contextlib.redirect_stdout(io.StringIO()):
                    summary.main()
                stats=json.loads((root/'summary/statistics.json').read_text())
                self.assertEqual(stats['methods']['cot']['parse_ok'],6)
                with patch.object(openai.ChatCompletion,'create',return_value={
                    'model':'mock','choices':[{'finish_reason':'stop','message':{'content':'Explanation only'}}]}):
                    run('llm','standard',root/'failure',1)
                bad=json.loads((root/'failure/cases/0000.json').read_text())
                self.assertEqual(bad['error_type'],'WaypointParseError')
                self.assertFalse(bad['waypoint_audit']['parse_ok'])
                self.assertNotIn('result',bad)
                mp=root/'standard/manifest.json'
                altered=json.loads(mp.read_text());altered['max_tokens']=99;mp.write_text(json.dumps(altered))
                with self.assertRaises(RuntimeError):
                    run('llm','standard',root/'standard')


if __name__=='__main__':
    unittest.main(verbosity=2)
