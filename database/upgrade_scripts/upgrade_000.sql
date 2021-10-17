-- natofortunato

-- New Traittype for number based merits/flaws
insert into TraitType (id, name, sheetspot, textbased) values ('pregdifnum', 'Pregi e Difetti', 'default', 0);
-- set natofortunato to new TraitType and update tracker type
update Trait set traittype = 'pregdifnum', trackertype = 1 where id = 'natofortunato';
-- update existing characters
update CharacterTrait set max_value = 3, cur_value = 3, text_value = '' where trait = 'natofortunato';