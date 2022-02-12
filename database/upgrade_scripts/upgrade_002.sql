--Make BotAdmin and Storyteller roles have to be explicitly removed before deleting an User

ALTER TABLE BotAdmin DROP FOREIGN KEY BotAdmin_ibfk_1;
ALTER TABLE BotAdmin ADD FOREIGN KEY (userid) REFERENCES People(userid)	ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE Storyteller DROP FOREIGN KEY Storyteller_ibfk_1;
ALTER TABLE Storyteller ADD FOREIGN KEY (userid) REFERENCES People(userid)	ON DELETE RESTRICT ON UPDATE CASCADE;

