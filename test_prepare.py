import unittest
from prepare import parse_lrc, choose_section, rank

class PreparationTests(unittest.TestCase):
    def test_multiple_lrc_timestamps_and_order(self):
        self.assertEqual(parse_lrc('[00:12.50][00:02.00]original line\n[ar:Tester]\n[00:08.20]next line'),[(2.0,'original line'),(8.2,'next line'),(12.5,'original line')])

    def test_window_has_25_to_35_seconds_of_whole_lines(self):
        lines=[(0,'intro')]+[(10+i*5,'original line '+str(i)) for i in range(12)]
        start,end,answer=choose_section(lines,180)
        self.assertTrue(25<=end-start<=35)
        self.assertTrue(4<=len(answer.splitlines())<=20)
        self.assertEqual(start,10)
        self.assertNotIn('original line 6',answer)

    def test_no_invented_timing_when_no_window(self):
        with self.assertRaises(ValueError): choose_section([(10,'one'),(40,'two')],180)

    def test_official_audio_beats_unofficial_lyrics(self):
        audio=dict(title='Song',channel='Artist - Topic')
        lyric=dict(title='Song Color Coded Lyrics',channel='Fan')
        cover=dict(title='Song official audio cover',channel='Fan')
        self.assertGreater(rank(audio),rank(lyric))
        self.assertGreater(rank(audio),rank(cover))

    def test_unrelated_topic_and_cover_are_rejected(self):
        song=dict(id=8,artist='버스커버스커',title='벚꽃엔딩')
        wrong=dict(title='Cherry Blossom Ending',channel='Pianica - Topic')
        right=dict(title='벚꽃 엔딩',channel='버스커버스커 BuskerBusker - Topic')
        cover=dict(title='Busker Busker Cherry Blossom Ending Piano Cover',channel='Player')
        self.assertEqual(rank(wrong,song),-1000)
        self.assertEqual(rank(cover,song),-1000)
        self.assertGreaterEqual(rank(right,song),100)

    def test_fast_hint_uses_density_without_inventing_words(self):
        lines=[(10+i*5,'a short line' if i<7 else 'many more words in this fast original passage') for i in range(16)]
        self.assertEqual(choose_section(lines,180)[0],10)
        start,end,answer=choose_section(lines,180,'1절 랩')
        self.assertGreaterEqual(start,30)
        self.assertTrue(all(line in [x[1] for x in lines] for line in answer.splitlines()))

if __name__=='__main__': unittest.main()
