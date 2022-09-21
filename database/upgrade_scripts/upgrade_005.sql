-- Game system tables

-- maintained by the  bot

create table Gamesystem(
	gamesystemid nvarchar(20) not null,
	primary key (gamesystemid)
)Engine=InnoDB;

-- maintained by users

create table ChannelGamesystem(
	channelid nvarchar(32) not null,
	gamesystemid nvarchar(20) not null,
	primary key (channelid),
	foreign key (gamesystemid) references Gamesystem(gamesystemid)
		on delete cascade
		on update cascade
)Engine=InnoDB;

ALTER TABLE Chronicle ADD gamesystemid nvarchar(20) DEFAULT NULL;
ALTER TABLE Chronicle ADD FOREIGN KEY (gamesystemid) REFERENCES Gamesystem(gamesystemid) ON DELETE SET NULL ON UPDATE CASCADE; 

/*
create table ChronicleRollSystem(
	chronicleid nvarchar(20) not null,
	rollsystemid nvarchar(20) not null,
	primary key (chronicleid),
	foreign key (chronicleid) references Chronicle(id)
		on delete cascade
		on update cascade,
	foreign key (rollsystemid) references RollSystem(rollsystemid)
		on delete cascade
		on update cascade
)Engine=InnoDB;*/