import os
from pathlib import Path
import unittest
import numpy as np
from organizer.embedding import Embedder


@unittest.skipUnless(os.environ.get('ORGANIZER_TEST_MODEL'), 'optional real model test; set ORGANIZER_TEST_MODEL to its local folder')
class SemanticTests(unittest.TestCase):
    def test_real_embedding_dimension_normalization_and_synonyms(self):
        e=Embedder(Path(os.environ['ORGANIZER_TEST_MODEL']))
        self.assertTrue(e.available,e.reason)
        vectors=e.encode(['automobile engine maintenance','repairing a car motor','baking sourdough bread'])
        self.assertEqual(vectors.shape,(3,384))
        np.testing.assert_allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-5)
        self.assertGreater(float(vectors[0]@vectors[1]),float(vectors[0]@vectors[2]))
