create table CharacterNotes(
	charid nvarchar(20) not null,
	userid nvarchar(32) not null,
    noteid nvarchar(50) not null,
    notetext TEXT(65535) default "",
	primary key (charid, userid, noteid),
	foreign key (charid) references PlayerCharacter(id)
		on delete cascade
		on update cascade,
	foreign key (userid) references People(userid)
		on delete cascade
		on update cascade
)Engine=InnoDB;
