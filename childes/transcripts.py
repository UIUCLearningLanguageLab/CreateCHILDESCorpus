import pandas as pd
import numpy as np
from cached_property import cached_property
import datetime
import spacy
import pyprind
import attr
import yaml
import re

from childes import config
from childes.params import Params
from childes.config import names_set, COLLOCATIONS

nlp = spacy.load('en_core_web_sm')

col2dtype = {'id': np.int,
             'speaker_role': str,
             'gloss': str,
             'type': str,
             'num_tokens': np.int,
             'transcript_id': np.int,
             'target_child_age': np.float,
             'target_child_sex': str,
             'collection_name': str}

# make sure to add spaces after each utterance boundary marker
punctuation_dict = {'imperative': '! ',
                    'imperative_emphatic': '! ',
                    'question exclamation': '! ',
                    'declarative': '. ',
                    'interruption': '. ',
                    'self interruption': '. ',
                    'quotation next line': '. ',
                    'quotation precedes': '. ',
                    'broken for coding': '. ',
                    'question': '? ',
                    'self interruption question': '? ',
                    'interruption question': '? ',
                    'trail off question': '? ',
                    'trail off': '. '}


class Transcripts:

    def __init__(self, params=None, sex=None):
        self.params = params or Params()

        # load each utterance as a row in original_transcripts frame
        dfs = [pd.read_csv(csv_path,
                           index_col='id',
                           usecols=col2dtype.keys(),
                           dtype=col2dtype)
               for csv_path in sorted(config.Dirs.original.glob('*.csv'))]
        self.df: pd.DataFrame = pd.concat(dfs)

        # drop rows
        print('Transcripts: Utterances before dropping rows: {:>8,}'.format(len(self.df)))
        self.df.drop(self.df[self.df['target_child_age'] > self.params.max_days].index, inplace=True)
        self.df.drop(self.df[self.df['num_tokens'] < self.params.min_utterance_length].index, inplace=True)
        self.df.drop(self.df[self.df['speaker_role'].isin(self.params.bad_speaker_roles)].index, inplace=True)
        self.df.drop(self.df[~self.df['collection_name'].isin(self.params.collection_names)].index, inplace=True)
        print('Transcripts: Utterances after  dropping rows: {:>8,}'.format(len(self.df)))

        if sex:
            self.df.drop(self.df[self.df['target_child_sex'] != sex].index, inplace=True)
            print('Transcripts: Utterances after  filter by sex: {:>8,}'.format(len(self.df)))

        self._ages = []

    @cached_property
    def age_ordered(self):
        res = []
        for age, rows in self.df.groupby('target_child_age'):
            for transcript_id, rows2 in rows.groupby('transcript_id'):

                transcript = ''
                for gloss, utterance_type in zip(rows2['gloss'], rows['type']):
                    if '�' in gloss or 'xxx' in gloss or 'www' in gloss:
                        continue
                    transcript += gloss
                    if self.params.punctuation:
                        transcript += punctuation_dict[utterance_type]

                res.append(transcript)

                self._ages.append(age)

        return res

    @cached_property
    def ages(self):
        _ = self.age_ordered
        return self._ages

    @property
    def num_transcripts(self):
        return len(self.age_ordered)


class PostProcessor:
    def __init__(self, params=None, verbose=False):
        self.params = params or Params()
        self.verbose = verbose

    def handle_titles(self, word):

        # replace name
        if word.text.lower() in names_set and self.params.normalize_names:
            res = config.Symbols.NAME

        # replace titled word
        elif word.text.istitle() and word.text not in {'I', 'Mother'} and self.params.normalize_titles:
            res = config.Symbols.TITLED

        else:
            res = word.text.lower()

        return res

    @staticmethod
    def fix_childes_coding(line):
        line = re.sub(r' chi chi ', ' child ', line)
        line = re.sub(r' chi ', ' child ', line)
        line = re.sub(r' mot ', ' mother ', line)
        line = re.sub(r' fat ', ' father ', line)
        return line

    @staticmethod
    def fix_spacy_tokenization(line):
        line = re.sub(r'valentine \'s day', 'valentines_day', line)
        line = re.sub(r'valentine \'s', 'valentines', line)
        line = re.sub(r'guy \'s', 'guys', line)
        line = re.sub(r'mommy\'ll', 'mommy will', line)
        line = re.sub(r'daddy\'ll', 'mommy will', line)
        line = re.sub(r'cann\'t', 'can not', line)
        line = re.sub(r' let \'s building', r' let us build', line)
        line = re.sub(r' let \'s looking', r' let us look', line)
        return line

    @staticmethod
    def replace_archaic_words(line):
        line = re.sub(r' oatios', ' oats', line)
        return line

    @staticmethod
    def replace_slang(line):
        line = re.sub(r' lets', ' let us', line)
        line = re.sub(r' djou', ' do you', line)
        line = re.sub(r' d\'you', ' do you', line)
        line = re.sub(r' didjou', ' did you', line)
        line = re.sub(r' wouldjou', ' would you', line)
        line = re.sub(r' whadyou', ' what do you', line)
        line = re.sub(r' whaddya', ' what do you', line)
        line = re.sub(r' whadya', ' what do you', line)
        line = re.sub(r' didja', ' did you', line)
        line = re.sub(r' gimme', ' give me', line)
        line = re.sub(r' comere', ' come here', line)
        line = re.sub(r' c\'mere', ' come here', line)
        line = re.sub(r' cmere', ' come here', line)
        line = re.sub(r' camere', ' come here', line)
        line = re.sub(r' c\'mon', ' come on', line)
        line = re.sub(r' comon', ' come on', line)
        line = re.sub(r' lookee', ' look', line)
        line = re.sub(r' looka', ' look', line)
        line = re.sub(r' mkay', ' okay', line)
        line = re.sub(r' whyn\'t', ' why do not you', line)
        line = re.sub(r' ya ', ' you ', line)
        line = re.sub(r' til ', ' until', line)
        line = re.sub(r' untill', ' until', line)
        line = re.sub(r' gon na', ' going to', line)
        line = re.sub(r' goin ', ' going ', line)
        line = re.sub(r' havta', ' have to', line)
        line = re.sub(r' oughta', ' ought to', line)
        line = re.sub(r' d\'ya', ' do you', line)
        line = re.sub(r' doin ', ' doing ', line)
        line = re.sub(r' cann\'t', ' can not', line)
        line = re.sub(r' dontcha', ' do not you', line)
        line = re.sub(r' getcha', ' get you', line)
        line = re.sub(r' howbout', ' how about', line)
        line = re.sub(r' scuse ', ' excuse ', line)
        line = re.sub(r' y\'know', ' you know', line)
        line = re.sub(r' ai n\'t', ' is not', line)
        line = re.sub(r' \'cause', ' because', line)
        line = re.sub(r' s\'more', ' some more', line)
        line = re.sub(r' got_to', ' got to', line)
        line = re.sub(r' aroun', ' around', line)
        return line

    @staticmethod
    def handle_spacy_contractions(line):
        """
        the input is a string from the spacy tokenizer.
        The spacy default tokenizer splits on contractions, meaning that tokens like "'ll" are
        whitespace-separated from tokens like "he".
        in order to use an SRL tagger, non-English tokens must be converted into English words.
        for example, "'ll" must be converted into "will".

        extra care is taken with the token "'s" because it can either be "is" or "us", depending on context.

        a possessive marker, like [POSS] is not introduced, as that is not how children experience English.
        hearing a sentence like "mommy's _", a child does not know if this is a possessive construction,
        or whether a verb will follow.
        thus, the corpus should not provide this additional information about what words come next.

        the regex "(\s|^)let" is used so that "let" is matched at beginning of transcript and
        anywhere inside of transcript but not as part of a larger word ending in "let"
        """

        # 's VERBing -> is VERBing
        line = re.sub(r'(\s|^)let \'s going to go', ' let us go', line)  # happens to end in -ing
        line = re.sub(r'(\s|^)let \'s bring', r' let us bring', line)  # happens to end in -ing
        line = re.sub(r'(\s|^)let \'s sing', r' let us sing', line)  # happens to end in -ing
        line = re.sub(r' \'s ([A-z]+?)ing', r' is \1ing', line)

        # contractions
        line = re.sub(r'(\s|^)let \'s', ' let us', line)
        line = re.sub(r' \'s got', ' has got', line)
        line = re.sub(r' \'m', ' am', line)
        line = re.sub(r' \'re', ' are', line)
        line = re.sub(r' \'ll', ' will', line)
        line = re.sub(r' \'d', ' would', line)
        line = re.sub(r' \'ve', ' have', line)
        line = re.sub(r' \'em', ' them', line)
        line = re.sub(r' n\'t', ' not', line)

        # possessive "'s"
        line = re.sub(r'\[NAME\] \'s', '[NAME_POSSESSIVE]', line)
        line = re.sub(r'\[NAME\] \'', '[NAME_POSSESSIVE]', line)  # in case a name ends with an "s"

        # all other "'s" should originate from "is"
        line = re.sub(r' \'s', ' is', line)

        # TODO this does not correctly handle case where "'s" is supposed to be "is", as in:
        # TODO  "your mommy's thirty eight" -> "your [NAME_POSSESSIVE] thirty eight"

        return line

    def process(self, transcripts, batch_size=100):
        """
        input is a list of unprocessed transcripts (each transcript is a string).
        output is a list of processed transcripts
        """

        num_transcripts = len(transcripts)
        print('Processor: Processing {} transcripts...'.format(num_transcripts))
        progress_bar = pyprind.ProgBar(num_transcripts)

        lines = []
        for doc in nlp.pipe(transcripts, batch_size=batch_size, disable=['tagger', 'parser', 'ner']):
            line = ' '.join([self.handle_titles(word) for word in doc])

            # co-locations - do this before processing names
            if self.params.merge_collocations:
                for w1, w2 in COLLOCATIONS:
                    line = re.sub(r'({}) ({})'.format(w1, w2), r'\1_\2', line)

            # regex substitutions
            line = self.fix_childes_coding(line)
            line = self.fix_spacy_tokenization(line)
            line = self.replace_archaic_words(line) if self.params.replace_archaic_words else line
            line = self.replace_slang(line) if self.params.replace_slang else line
            line = self.handle_spacy_contractions(line) if self.params.handle_spacy_contractions else line

            if ' let is ' in line:
                print(line)
                raise SystemError('Found disallowed substring in processed transcript')

            lines.append(line)
            progress_bar.update()

        return lines

    def to_file(self, texts, ages, path_to_folder=None, suffix='', dry_run=False):
        print('Processor: Writing to disk...')
        date_str = datetime.datetime.now().strftime('%Y%m%d')
        corpus_name = 'childes-{}'.format(date_str)

        if path_to_folder is None:
            path_to_folder = config.Dirs.corpora
        if dry_run:
            path_to_folder = config.Dirs.corpora / 'dry_runs'

        params_path = path_to_folder / '{}_{}{}.yaml'.format(corpus_name, 'params', suffix)
        terms_path = path_to_folder / '{}_{}{}.txt'.format(corpus_name, 'terms', suffix)
        ages_path = path_to_folder / '{}_{}{}.txt'.format(corpus_name, 'ages', suffix)

        f1 = terms_path.open('w', encoding='utf-8')
        f2 = ages_path.open('w', encoding='utf-8')

        for text, age in zip(texts, ages):
            f1.write(text + '\n')
            f2.write(str(age) + '\n')

        f1.close()
        f2.close()

        # save params
        with params_path.open('w', encoding='utf8') as f:
            yaml.dump(attr.asdict(self.params), f, default_flow_style=False, allow_unicode=True)
