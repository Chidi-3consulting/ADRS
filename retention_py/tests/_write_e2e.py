# Helper script to write E2E test file - run with: python tests/_write_e2e.py
import os

content = open(os.path.join(os.path.dirname(__file__), '_e2e_content.py'), 'r', encoding='utf-8').read()
out = os.path.join(os.path.dirname(__file__), 'test_e2e_workflow.py')
with open(out, 'w', encoding='utf-8') as f:
    f.write(content)
print('Written to:', out)
