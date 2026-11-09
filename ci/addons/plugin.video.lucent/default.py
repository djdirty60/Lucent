# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0].rsplit("\\", 1)[0] + "/resources/lib")
import router  # noqa: E402

router.run(sys.argv)
