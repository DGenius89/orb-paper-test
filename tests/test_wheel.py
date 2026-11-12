import os, sys, unittest
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
import wheel


class Wheel(unittest.TestCase):
    def test_parse_both_cboe_formats(self):
        a = "Cboe disclaimer text\nDATE,PUT\n06/30/1986,100.00\n07/01/1986,100.5\n"
        b = "DATE,OPEN,HIGH,LOW,CLOSE\n2020-01-02,1,1,1,3245.5\n2020-01-03,1,1,1,\"3,234.8\"\n"
        self.assertEqual(wheel.parse_cboe(a), [(date(1986, 6, 30), 100.0), (date(1986, 7, 1), 100.5)])
        self.assertEqual(wheel.parse_cboe(b)[1], (date(2020, 1, 3), 3234.8))

    def test_yearly_uses_prior_year_end(self):
        s = [(date(2019, 12, 31), 100.0), (date(2020, 6, 1), 90.0), (date(2020, 12, 31), 110.0),
             (date(2021, 12, 31), 99.0)]
        self.assertEqual(wheel.yearly(s), {2020: 10.0, 2021: -10.0})


if __name__ == "__main__":
    unittest.main()
