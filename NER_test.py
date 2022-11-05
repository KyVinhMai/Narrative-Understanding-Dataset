import re
import textwrap
import copy
import spacy
import spacy_transformers
nlp = spacy.load('en_core_web_trf')

text = ("The Queen Of Scots once said that a man musn't fight unless needed. Long ago in a kingdom far away--specifically, in Elsinore, Denmark--some guys named Bernardo and Francisco are hanging out on the castle battlements. "
        "Francisco is done with his shift and gets ready to head out. Marcellus, yet another watchman, shows up with a man named Horatio. Because it's dark outside,"
        "no one can see anything, much less each other, so there's a lot of \"who's there?\" and \"what?\" and, in one very interesting case, \"holla!\" Everyone starts talking "
        "about a mysterious \"thing\" that's been appearing lately, and by lately, we mean the last two nights. Bernardo starts to explain what he saw. It was a... Just then, a ghost shows up."
        " The guards all think the ghost looks suspiciously like the recently deceased King of Denmark, especially around the eyes. Everyone tells Horatio to talk to the ghost, since he's the scholar in the group . "
        "Horatio asks the ghost a few questions which are apparently offensive, as the ghost walks off without answering. To further confirm that the ghost is the image of the dead King, "
        "Horatio remarks that it was wearing the same armor the King wore when fighting Norway. Everyone's got a bad feeling about this, and to try to make sense of it, Marcellus asks Horatio for a little history lesson."
        " We learn that, a while back, Old King Hamlet made a little wager with the King of Norway about who could kill the other person first in combat. Gee, that sounds safe. "
        "Old King Hamlet won so he got to take a bunch of Norway's land. The king of Norway's son, young Fortinbras, has raised an army to get his family's land back. "
        "He also wants revenge for his dad's death, naturally. Hm, we're already sensing a theme. Because the kingdom of Denmark is preparing for war with Norway, "
        "Horatio's number one concern is that a dead man walking about in ghost form might be a sign that Denmark is going to lose. Horatio is busy detailing just how bad an omen this is, "
        "with many references to Julius Caesar's death and all the nasty things that came before it, when the ghost comes back. The guards want the ghost to stay and speak, so they try to hit it to make it stand still. "
        "Unfortunately, they can't really keep it in their sights long enough to land any blows. Then they rehash events: they were silly for trying to strike at the ghost, and the ghost was probably going to say something,"
        " except the cock crowed and scared it off. "
        "Horatio suggests they tell Prince Hamlet about the ghost that looks an awful lot like his father. Maybe Hamlet will know what to do, because these guys sure don't.")

class Label_entities():
    def __init__(self, text: str):
        self.text = copy.deepcopy(text)
        self.doc = nlp(text)
        self.ents = [(e.text, e.start_char, e.end_char, e.label_) for e in self.doc.ents]
        self.persons = dict() # Character subs
        self.location_subs = dict()

    def identify_names(self) -> None:
        def name_key_validation(name) -> True:
            "Checks if the name is in the dictionary. Including the first name if it is a full name"
            name = str(name)
            if name in self.persons:
                return False

            if " " in name:
                if name.split(" ")[0] in self.persons: # Check the first name of a full name
                    return False

            return True

        num = 0
        for word in self.doc.ents:
            if word.label_ == "PERSON" and name_key_validation(word):
                self.persons[str(word)] = f"|__CHARACTER{num}__|"
                num += 1

    def replace_names(self) -> None:
        for person in self.persons:
            self.text = self.text.replace(person, self.persons[person])

    def add_character_list(self):
        readable_dict = {}
        for person in self.persons.keys():
            readable_dict[person] = f"Char {self.persons[person][12]}"

        self.text = self.text + "\n\n" + f"Character List: {readable_dict}"

    def create_text_file(self):
        self.identify_names()
        self.replace_names()
        self.add_character_list()

        return self.text

sub_file = Label_entities(text)
new_file = sub_file.create_text_file()
print(new_file)