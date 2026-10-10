"""Reproducible source inventory, not a language-independent complexity score."""
import difflib
import re
from pathlib import Path
from .core import scaffold, digest_tree

MAX_DIFF_LINE_PRODUCT=2_000_000
MAX_DIFF_LINES=100_000

CODE_SUFFIXES={'.rb','.rs','.py','.ts','.tsx','.js','.jsx','.cs','.kt','.hs','.sh','.ex','.exs'}

def is_test_path(path):
    path=Path(path)
    return any(part.lower() in ('test','tests','spec','specs','__tests__') for part in path.parts[:-1]) or path.stem.lower().startswith(('test_','spec_')) or path.stem.lower().endswith(('_test','_spec')) or path.stem.lower() in ('test','spec')

def source_files(root):
    root=Path(root)
    if not root.is_dir():raise ValueError('source tree is missing')
    digest_tree(root)  # Reject symlinks/special files and enforce artifact bounds.
    return {p.relative_to(root).as_posix():p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}

def inventory(root,baseline=None):
    files=source_files(root);original=source_files(baseline) if baseline is not None else {}
    groups={name:{'files':0,'bytes':0,'physical_lines':0,'nonblank_lines':0,'comment_only_lines_heuristic':0} for name in ('production','tests','mixed_production_and_tests','noncode')}
    details=[];added=removed=0;diff_unavailable=[]
    for name,data in files.items():
        category='noncode' if Path(name).suffix not in CODE_SUFFIXES else 'tests' if is_test_path(name) else 'production'
        text=data.decode('utf-8',errors='replace')
        if category=='production' and Path(name).suffix=='.rs' and re.search(r'#\s*\[\s*(?:cfg\s*\(\s*test\s*\)|test)\s*\]',text):
            category='mixed_production_and_tests'
        lines=text.splitlines()
        # Full-line comment prefixes only; no claim to parse multiline strings or embedded tests.
        prefix=('#',) if Path(name).suffix in ('.rb','.py','.sh','.ex','.exs') else ('--',) if Path(name).suffix=='.hs' else ('//','/*','*','*/')
        metrics={'files':1,'bytes':len(data),'physical_lines':len(lines),'nonblank_lines':sum(bool(line.strip()) for line in lines),
                 'comment_only_lines_heuristic':sum(bool(line.strip()) and line.lstrip().startswith(prefix) for line in lines)}
        for key,value in metrics.items():groups[category][key]+=value
        details.append({'path':name,'category':category,**metrics})
    if baseline is not None:
        for name in sorted(files.keys()|original.keys()):
            before=original.get(name,b'').decode('utf-8',errors='replace').splitlines()
            after=files.get(name,b'').decode('utf-8',errors='replace').splitlines()
            if before==after:continue
            if len(before)+len(after)>MAX_DIFF_LINES or len(before)*len(after)>MAX_DIFF_LINE_PRODUCT:
                diff_unavailable.append(name)
                continue
            for tag,i,j,k,l in difflib.SequenceMatcher(a=before,b=after,autojunk=False).get_opcodes():
                if tag in ('replace','delete'):removed+=j-i
                if tag in ('replace','insert'):added+=l-k
    return {'source_sha256':digest_tree(root),'groups':groups,'files':details,
            'changed_lines_vs_starter':({'available':False,'reason':'exact_diff_work_limit','files':diff_unavailable,'added':None,'removed':None,'total':None} if diff_unavailable else {'added':added,'removed':removed,'total':added+removed}) if baseline is not None else None}

def measure(task,language,result_path=None):
    import json
    starter=scaffold(task,language)/'src'
    report={'schema_version':1,'task':task,'language':language,'starter':inventory(starter),
            'reference':inventory(scaffold(task,language,'reference')/'src',starter),
            'definitions':{'physical':'splitlines(), including blanks and comments; final newline adds no extra line.',
                           'tests':'Path/filename heuristic; Rust files with cfg(test)/test attributes are reported as mixed production+tests, not split into exact test LOC.',
                           'comments':'Full-line language-prefix heuristic; not a parser, may misclassify multiline strings.',
                           'change':'Difflib added+removed lines against same-language starter; unchanged scaffold is not attributed to the agent.',
                           'limits':'LOC is not semantic complexity, difficulty, quality, or a cross-language productivity ranking.'}}
    if result_path is not None:
        path=Path(result_path);result=json.loads(path.read_text());manifest=result.get('manifest') or {}
        if manifest.get('task')!=task or manifest.get('language')!=language:raise ValueError('result treatment does not match requested task/language')
        invocations=(result.get('collection') or result.get('partial_collection') or {}).get('invocations',[])
        observed=[i for i in invocations if i.get('artifact_available')]
        for label,invocation in [('initial_handoff',next((i for i in observed if i['index']==0),None)),('final_handoff',observed[-1] if observed else None)]:
            if invocation is not None:
                report[label]={'index':invocation['index'],'status':invocation['status'],**inventory(path.parent/'collection'/f"snapshot-{invocation['index']}"/'src',starter)}
        report['tests_condition']=manifest.get('tests')
        report['supplied_tests']='T1 supplies public_cases.json and test_public.py outside src; these are support artifacts, excluded from source LOC.'
    return report
