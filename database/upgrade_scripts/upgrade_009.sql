ALTER TABLE GameSession ADD gamestateid SMALLINT NOT NULL DEFAULT 0;

DROP TABLE IF EXISTS TraitSettings;

CREATE TABLE TraitSetting (
    traitid varchar(20) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci not null, 
    gamesystemid varchar(20) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci not null,
    gamestateid smallint not null,
    rollpermanent BOOLEAN not null DEFAULT 0,
    autopenalty BOOLEAN not null DEFAULT 0,
    primary key (traitid, gamesystemid, gamestateid),
    foreign key (traitid) references Trait(id)
        on update cascade
        on delete cascade,
    foreign key (gamesystemid) references Gamesystem(gamesystemid)
        on update cascade
        on delete cascade
)
    Engine=InnoDB 
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_general_ci
    ;

INSERT INTO TraitSetting (traitid, gamesystemid, gamestateid, rollpermanent, autopenalty)
SELECT t.id, gs.gamesystemid, 1, 0, 1
FROM Trait t
JOIN TraitType tt ON (tt.id = t.traittype)
JOIN Gamesystem gs
WHERE tt.id in ('capacita', 'conoscenza', 'attitudine')
AND gs.gamesystemid in ('V20_VTM_HOMEBREW_00', 'V20_VTM_VANILLA');

INSERT INTO TraitSetting (traitid, gamesystemid, gamestateid, rollpermanent, autopenalty)
VALUES 
('volonta', 'V20_VTM_VANILLA',     0, 1, 0),
('volonta', 'V20_VTM_VANILLA',     1, 1, 0),
('volonta', 'V20_VTM_HOMEBREW_00', 0, 1, 0),
('volonta', 'V20_VTM_HOMEBREW_00', 1, 0, 0);

INSERT INTO TraitSetting (traitid, gamesystemid, gamestateid, rollpermanent, autopenalty)
VALUES
('forza', 'V20_VTM_VANILLA', 1, 0, 1);
