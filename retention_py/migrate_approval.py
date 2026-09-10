import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'retention.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cols = [r[1] for r in cur.execute('PRAGMA table_info(data_categories)').fetchall()]
print('Existing cols:', cols)

if 'data_classification' not in cols:
    cur.execute("ALTER TABLE data_categories ADD COLUMN data_classification VARCHAR(50) DEFAULT 'standard'")
    print('Added data_classification column')

if 'approval_type' not in cols:
    cur.execute("ALTER TABLE data_categories ADD COLUMN approval_type VARCHAR(50) DEFAULT 'single_approval'")
    print('Added approval_type column')

# Update approval_type according to requires_dual_approval
cur.execute("UPDATE data_categories SET approval_type = 'dual_approval' WHERE requires_dual_approval = 1")
cur.execute("UPDATE data_categories SET approval_type = 'single_approval' WHERE requires_dual_approval = 0 AND (approval_type IS NULL OR approval_type = '')")

# Classify categories by name
cur.execute("UPDATE data_categories SET data_classification = 'special_category' WHERE lower(name) LIKE '%biometric%' OR lower(name) LIKE '%health%' OR lower(name) LIKE '%medical%'")
cur.execute("UPDATE data_categories SET data_classification = 'children' WHERE lower(name) LIKE '%children%' OR lower(name) LIKE '%minor%'")
cur.execute("UPDATE data_categories SET data_classification = 'financial_aml' WHERE lower(name) LIKE '%tax%' OR lower(name) LIKE '%invoice%' OR lower(name) LIKE '%audit%' OR lower(name) LIKE '%banking%' OR lower(name) LIKE '%kyc%'")
cur.execute("UPDATE data_categories SET data_classification = 'confidential' WHERE lower(name) LIKE '%whistleblowing%' OR lower(name) LIKE '%grievance%' OR lower(name) LIKE '%employee%'")
cur.execute("UPDATE data_categories SET data_classification = 'standard' WHERE data_classification IS NULL OR data_classification = ''")

# Category 17 is standard and can be auto_disposal
cur.execute("UPDATE data_categories SET data_classification = 'standard', approval_type = 'auto_disposal' WHERE id = 17")

conn.commit()
print('Migration complete!')
for row in cur.execute('SELECT id, name, data_classification, approval_type, requires_dual_approval FROM data_categories LIMIT 10').fetchall():
    print(row)
conn.close()
