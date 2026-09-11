import hashlib,json,unittest
from pathlib import Path
class PackagingTests(unittest.TestCase):
 def test_addon_sources_match_and_manifest_is_not_overwritten(self):
  root=Path(__file__).resolve().parent;out=root/'homeassistant/addon/source'
  hashes=json.loads((out/'SOURCE-HASHES.json').read_text())
  self.assertIn('name',json.loads((out/'manifest.json').read_text()))
  for name,digest in hashes.items():
   self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest,name)
   self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest,name)
  self.assertEqual(len([p for p in out.iterdir() if p.is_file()]),len(hashes)+1)
if __name__=='__main__':unittest.main()
