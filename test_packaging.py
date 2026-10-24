import hashlib,json,unittest
from pathlib import Path
class PackagingTests(unittest.TestCase):
 def test_addon_sources_match_and_manifest_is_not_overwritten(self):
  root=Path(__file__).resolve().parent;out=root/'homeassistant/addon/source'
  mirror=root/'aldes_pilot';mirror_source=mirror/'source'
  hashes=json.loads((out/'SOURCE-HASHES.json').read_text())
  self.assertIn('name',json.loads((out/'manifest.json').read_text()))
  for name,digest in hashes.items():
   self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest,name)
   self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest,name)
   self.assertEqual(hashlib.sha256((mirror_source/name).read_bytes()).hexdigest(),digest,name)
  self.assertEqual(len([p for p in out.iterdir() if p.is_file()]),len(hashes)+1)
  for name in ('config.yaml','Dockerfile','run.py','container_run.py','.dockerignore'):
   self.assertEqual((mirror/name).read_bytes(),(root/'homeassistant/addon'/name).read_bytes(),name)
  self.assertEqual(len([p for p in mirror_source.iterdir() if p.is_file()]),len(hashes)+1)
  self.assertEqual(len([p for p in mirror.iterdir() if p.is_file()]),5)
if __name__=='__main__':unittest.main()
