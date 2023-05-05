import random

import warnings

import os

import Dataloaders as dl
import settings

import numpy as np
random.seed(42)
np.random.seed(42)

from collections import Counter

from entity_replacement import EntityReplacer

import character_list_generator as clg

class RecognitionQuestion:

    def __init__(self, correct_answer, decoys, decoy_types, when_asked, retention_delay):

        self.correct_answer = correct_answer
        self.decoys = decoys
        self.decoy_types = decoy_types
        self.when_asked = when_asked
        self.retention_delay = retention_delay

        self.is_mixed = True if len(set(decoy_types)) > 1 else False

        self.question_type = "mixed" if self.is_mixed else self.decoy_types[0]

        self.n_options = len(self.decoys) + 1
        self.true_ans_position = np.random.randint(self.n_options)

        self.all_options = decoys.copy()
        self.all_options.insert(self.true_ans_position, correct_answer)

    def question_string(self):
        return "".join(["Which of the following scenes was in the book?\n"] + [str(i + 1) + ") " + self.all_options[i] + "\n" for i in range(self.n_options)])

    def answer(self):
        return str(self.true_ans_position + 1)
    def detailed_question_string(self):

        description = "A {} decoy type recognition question:\n".format(self.question_type)


        answer_options = []
        i = 0
        dec_i = 0
        while i < self.n_options:
            if i != self.true_ans_position:
                answer_options.append("({} decoy) ".format(self.decoy_types[dec_i]) + str(i + 1) + ") " + self.all_options[i] + "\n")
                dec_i += 1
            else:
                answer_options.append("(True answer) " + str(i + 1) + ") " + self.all_options[i] + "\n")

            i += 1


        question = "".join(["Which of the following scenes was in the book?\n"] + answer_options)

        return description + question

    def __str__(self):

        answer = "Answer:" + str(self.true_ans_position + 1)

        return self.question_string() + answer

    def __repr__(self):

        return self.detailed_question_string()

    def IsComplete(self):
        '''Since some summaries or false summaries might have been None (GPT failed to generate them),
        we need to filter out questions that got affected by that'''
        if self.correct_answer is None or any([el is None for el in self.decoys]):
            return False
        else:
            return True

class RecognitionQuestionGenerator:

    def __init__(self, book_processor, parallel_books=None, ent_rep_dict=None):
        '''Takes a book processor (already with true and fake summaries generated. Generates questions based on that.'''
        self.book_processor = book_processor
        self.parallel_books = parallel_books ### A list of book processor objects, to draw decoy answers from. Only relevant for the "other book" type of recognition decoys.

        self.questions = [] # A list that stores a list of RecognitionQuestion objects as its elements.
        self.read_progress = 0 # Index of the last read chunk.

        self.book_length = len(self.book_processor.book_chunk_summaries)

        # By default, false summaries may have None values where false summary generation failed
        self.false_summaries_filtered = [[s for s in fs if s] for fs in self.book_processor.false_book_chunk_summaries] # Remove all None summaries
        self.false_summary_chunk_weights = np.array([len(el) for el in self.false_summaries_filtered])

        if np.sum(self.false_summary_chunk_weights) <= 0.5:
            raise ValueError("No false summaries available for this book.")
        if np.sum(self.false_summary_chunk_weights) <= 10.5:
            warnings.warn("Few false summaries available for the current book.")

        self.ent_rep_dict = ent_rep_dict
        # Create self.entity replacer?

        # self.suspicious_true_summary_idx = set()
        # for idx, warning in self.book_processor.failed_summaries.items():
        #     if warning != "Failed to create any fake summaries.":
        #         self.suspicious_true_summary_idx.add(idx)

    def advance(self):

        current_questions = []
        for _ in range(settings.lookahead_questions_per_step):
            q = self.generate_lookahead_question()
            if q and RecognitionQuestion.IsComplete(q):
                current_questions.append(q)

        for _ in range(settings.scene_negation_questions_per_step):
            q = self.generate_scene_negation_question()

            if q and RecognitionQuestion.IsComplete(q):
                current_questions.append(q)

        for _ in range(settings.other_book_questions_per_step):
            q = self.generate_other_book_question()

            if q and RecognitionQuestion.IsComplete(q):
                current_questions.append(q)

        self.read_progress += 1
        self.questions.append(current_questions)

    def generate_lookahead_question(self):
        if self.read_progress > self.book_length - (settings.number_of_decoy_options + 1):
            return None # Can not generate lookahead questions too close to the end of the book
        else:

            decoy_id_candidates = np.arange(self.read_progress + 1, self.book_length)
            #decoy_id_candidates = [i for i in decoy_id_candidates if i not in self.suspicious_true_summary_idx] # Can be used for more strict filtering
            decoy_ids = np.random.choice(decoy_id_candidates, settings.number_of_decoy_options, replace=False)

            true_ans, true_idx = self.get_random_summary(self.read_progress + 1)

            true_ans = self.book_processor.book_chunk_summaries[true_idx]

            decoys = [self.book_processor.book_chunk_summaries[id] for id in decoy_ids]
            decoy_types = ["Lookahead" for _ in decoy_ids]



            return RecognitionQuestion(correct_answer=true_ans, decoys=decoys, decoy_types=decoy_types,
                                       when_asked=self.read_progress, retention_delay=self.read_progress-true_idx)

    def generate_scene_negation_question(self):

        available_fake_weights = self.false_summary_chunk_weights[:self.read_progress + 1].copy()

        if np.sum(available_fake_weights) < settings.number_of_decoy_options:
            return None
        else:

            decoys = []


            idx_to_numpicks = Counter()
            for _ in range(settings.number_of_decoy_options):

                fake_weights_normalized = available_fake_weights / np.sum(available_fake_weights)

                chunk_choice = np.random.choice(np.arange(self.read_progress + 1), p=fake_weights_normalized)
                available_fake_weights[chunk_choice] -= 1

                idx_to_numpicks[chunk_choice] += 1

            for chunk, numpicks in idx_to_numpicks.items():
                decoys_from_chunk = np.random.choice(self.false_summaries_filtered[chunk], numpicks, replace=False)
                decoys.extend(decoys_from_chunk)

            np.random.shuffle(decoys) # Otherwise decoys from the same chunk would be close
            decoy_types = ["Change" for _ in range(settings.number_of_decoy_options)]

            true_ans, true_idx = self.get_random_summary(self.read_progress + 1)

        return RecognitionQuestion(true_ans, decoys, decoy_types, when_asked=self.read_progress, retention_delay=self.read_progress-true_idx)

    def get_random_summary(self, sample_up_to=None):

        if sample_up_to is None:
            sample_up_to = self.book_length

        #candidates = [i for i in range(sample_up_to) if i not in self.suspicious_true_summary_idx]
        #if not candidates:
        #    raise ValueError("No good chunk summaries to sample from")
        # Handled through "is complete" in the question class
        candidates = np.arange(sample_up_to)



        true_idx = np.random.choice(candidates) #np.random.randint(self.read_progress + 1)
        # Just add "filter" here?
        true_ans = self.book_processor.book_chunk_summaries[true_idx]
        return true_ans, true_idx
    def generate_other_book_question(self):

        true_idx = np.random.randint(self.read_progress + 1)
        true_ans = self.book_processor.book_chunk_summaries[true_idx] # Use get random summary here

        decoy_books = np.random.choice(np.arange(len(self.parallel_books)), size=settings.number_of_decoy_options, replace=False)
        decoy_books = [self.parallel_books[i] for i in decoy_books]
        decoys = [el.get_random_summary()[0] for el in decoy_books]

        ### Substitute entities from this book into entities from another.
        decoys = [EntityReplacer.sub_nonrandom_characters(self.ent_rep_dict, b.ent_rep_dict, text=d) for d, b in zip(decoys, decoy_books)]

        decoy_types = ["Otherbook" for _ in range(settings.number_of_decoy_options)]

        return RecognitionQuestion(true_ans, decoys, decoy_types, when_asked=self.read_progress, retention_delay=self.read_progress-true_idx)

    def set_parallel_books(self, pb):
        '''Each PB is also a question generator'''
        self.parallel_books = pb

    def generate_questions(self):

        while self.read_progress < self.book_length:
            self.advance()


def process_folder(summary_folder, num_to_process=5):
    sumpath = os.path.join("Data", summary_folder)
    summaries_to_process = [os.path.join(sumpath, f) for f in os.listdir(sumpath) if os.path.isfile(os.path.join(sumpath, f))][0:num_to_process]

    summaries_to_process = summaries_to_process[:num_to_process]

    book_processors = [dl.BookProcessor.init_from_summaries(s) for s in summaries_to_process]
    ent_rep_dicts = [clg.get_counts_and_subs(b.original_book_text)[1] for b in book_processors]

    question_generators = [RecognitionQuestionGenerator(b, ent_rep_dict=ent_rep_dicts[i]) for i, b in enumerate(book_processors)]

    for i, g in enumerate(question_generators):

        g.set_parallel_books(question_generators[0:i] + question_generators[i+1:])


    return question_generators



if __name__ == "__main__":

    # Individual book processors - okay for false summary and lookahead question types, not ok for summaries from other books

    if False:

        b = dl.BookProcessor.init_from_summaries("./Data/ScifiExample25chunks.tagseparated")
        _, ent_rep_dict = clg.get_counts_and_subs(b.original_book_text)

        question_generator = RecognitionQuestionGenerator(b, ent_rep_dict=ent_rep_dict)


        tmp_other_books = [question_generator, question_generator, question_generator, question_generator, question_generator]
        question_generator.set_parallel_books(tmp_other_books)

        question_generator.generate_questions()

        print(question_generator.questions[0])

    qgs = process_folder("TrueAndFalseSummaryData")



