from datasets import load_dataset
from transformers import AutoTokenizer
import Dataloaders as dl

from datasets import Dataset
from torch.utils.data import DataLoader

import pickle as pkl

import numpy as np
import evaluate

import re

import entity_replacement

from entity_replacement import EntityReplacer
sub_rc = EntityReplacer.sub_random_characters

metric = evaluate.load("accuracy")

import torch as t
device = t.device("cuda") if t.cuda.is_available() else t.device("cpu")

import os

from utils.helper_functions import PreppedQuestions, read_shortform_questions

def compute_metrics(eval_pred):

    logits, labels = eval_pred

    predictions = np.argmax(logits, axis=-1)

    return metric.compute(predictions=predictions, references=labels)

def my_gen():

    for _ in range(1, 1000):

        num = np.random.choice(np.arange(100))

        yield {"text": "The number is {}. Is it odd?".format(num), "label": num % 2}


# def get_all_change_questions_nocontext(files, shuffle=True):
#
#     '''Gets a few random questions (usually 3), associated with a specific reading time in a random book'''
#     if shuffle:
#         np.random.shuffle(files)
#
#
#     for p in files:
#
#
#         questions = read_shortform_questions(p)
#
#
#         for qsts, anss, types in zip(questions.questions, questions.answers, questions.question_types):
#
#             for q, a, t in zip(qsts, anss, types):
#                 if t == "Change":
#                     q = re.sub("(Which of the following scenes was in the book\?\\n| of the above.\\n)", "", q)
#                     yield {"text": q, "label": int(a)}

def get_all_change_questions_nocontext(files, shuffle=True):

    '''Gets a few random questions (usually 3), associated with a specific reading time in a random book'''
    if shuffle:
        np.random.shuffle(files)


    for p in files:


        questions = read_shortform_questions(p)


        for qsts, anss, types in zip(questions.questions, questions.answers, questions.question_types):

            for q, a, t in zip(qsts, anss, types):
                if t == "Change":
                #if t == "Otherbook":

                    q = re.sub("Which of the following scenes was in the book\?\\n|\\n6\) None of the above.\\n", "", q)
                    q = re.sub("1\) |\\n2\) |\\n3\) |\\n4\) |\\n5\) ", "|", q)
                    yield {"text": q, "label": int(a)-1}



#path = os.path.join("Data", "TmpQuestionsBackup", "raw", "shortform")
path = os.path.join("Data", "TmpQuestionsBackup", "substituted", "shortform")
root, dirs, files = next(os.walk(path))

all_q_files = [os.path.join(root, f) for f in files]
#
# dataset_train = Dataset.from_generator(lambda: my_tf_sum_gen(all_truefalse_sum_files[0:700])) # Lambda since it wants a generator function, not a generator object
# dataset_test = Dataset.from_generator(lambda: my_tf_sum_gen(all_truefalse_sum_files[700:]))

#
# dataset_train = Dataset.from_generator(lambda: my_tf_sum_gen(all_truefalse_sum_files[0:100])) # Lambda since it wants a generator function, not a generator object
# dataset_test = Dataset.from_generator(lambda: my_tf_sum_gen(all_truefalse_sum_files[100:125]))

indices = list(range(1000))
np.random.shuffle(indices) # Have to shuffle here because of a weird batched dataset bug

# dataset_train = Dataset.from_generator(lambda: my_tf_sum_gen_substituted([all_truefalse_sum_files[ind] for ind in indices[0:700]])) # Lambda since it wants a generator function, not a generator object
# dataset_test = Dataset.from_generator(lambda: my_tf_sum_gen_substituted([all_truefalse_sum_files[ind] for ind in indices[700:1000]]))

# dataset_train = Dataset.from_generator(lambda: get_all_change_questions_nocontext([all_q_files[ind] for ind in indices[0:700]])) # Lambda since it wants a generator function, not a generator object
# dataset_test = Dataset.from_generator(lambda: get_all_change_questions_nocontext([all_q_files[ind] for ind in indices[700:1000]]))


dataset_train = Dataset.from_generator(lambda: get_all_change_questions_nocontext(all_q_files[0:700])) # Lambda since it wants a generator function, not a generator object
dataset_test = Dataset.from_generator(lambda: get_all_change_questions_nocontext(all_q_files[700:1000]))

tokenizer = AutoTokenizer.from_pretrained("bert-base-cased")

def tokenize_function(examples):

    return tokenizer(examples["text"], padding="max_length", truncation=False) # CHANGE TO TRUE IF YOU WANT A LARGER DS

tokenized_dataset_train = dataset_train.map(tokenize_function, batched=True)
tokenized_dataset_test = dataset_test.map(tokenize_function, batched=True)

if True:
    tokenized_dataset_train = tokenized_dataset_train.filter(lambda el: len(el["input_ids"]) <= 512)
    tokenized_dataset_test = tokenized_dataset_test.filter(lambda el: len(el["input_ids"]) <= 512)


from transformers import AutoModelForSequenceClassification
model = AutoModelForSequenceClassification.from_pretrained("bert-base-cased", num_labels=6) # Num labels should be 6! (depends on how stuff is counted however, and should not actually matter.

from transformers import TrainingArguments, Trainer

training_args = TrainingArguments(output_dir="test_nocontext_trainer", evaluation_strategy="epoch")


model.to(device)

# trainer = Trainer(
#     model=model,
#     args=training_args,
#     train_dataset=tokenized_datasets,
#     eval_dataset=tokenized_datasets,
#     compute_metrics=compute_metrics,
#
# )
#
# trainer.train()


# Trying to train with pytorch instead
tokenized_dataset_train = tokenized_dataset_train.remove_columns(["text"])
tokenized_dataset_train = tokenized_dataset_train.rename_column("label", "labels")
tokenized_dataset_train.set_format("torch")

tokenized_dataset_test = tokenized_dataset_test.remove_columns(["text"])
tokenized_dataset_test = tokenized_dataset_test.rename_column("label", "labels")
tokenized_dataset_test.set_format("torch")






train_dataloader = DataLoader(tokenized_dataset_train, shuffle=False, batch_size=24)
eval_dataloader = DataLoader(tokenized_dataset_test, batch_size=24)

from torch.optim import AdamW
optimizer = AdamW(model.parameters(), lr=5e-5)

from transformers import get_scheduler
num_epochs = 3
num_training_steps = num_epochs * len(train_dataloader)

lr_scheduler = get_scheduler(name="linear", optimizer=optimizer, num_warmup_steps=0, num_training_steps=num_training_steps)

from tqdm.auto import tqdm
progress_bar = tqdm(range(num_training_steps))



metric = evaluate.load("accuracy")

accuracies = []

for epoch in range(num_epochs):

    model.train()

    for batch in train_dataloader:

        batch = {k: v.to(device) for k, v in batch.items()}
        outputs = model(**batch)
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        lr_scheduler.step()
        optimizer.zero_grad()
        progress_bar.update(1)

    model.eval()
    for batch in eval_dataloader:
        batch = {k: v.to(device) for k, v in batch.items()}

        with t.no_grad():
            outputs = model(**batch)

        logits = outputs.logits
        predictions = t.argmax(logits, dim=-1)
        metric.add_batch(predictions=predictions, references=batch["labels"])


    accuracies.append(metric.compute())
    print("Accuracy: {}".format(accuracies[-1]))