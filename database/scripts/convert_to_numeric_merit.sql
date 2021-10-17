-- use this to update a merit/flaw from the regular textbased type to the numeric type
-- requires upgrade 000 to work

set @traitid = 'novevite'; -- trait to update
set @ttype = 1; -- type of numeric tracker: 0 = no tracker, 1 = bounded tracker, 1 = dabmage tracker, 3 = unbounded tracker
set @traitval = 9; -- max/initial value of the trait

-- update trait
update Trait set traittype = 'pregdifnum', trackertype = @ttype where id = @traitid and traittype = 'pregdif';
-- update existing characters
update CharacterTrait set max_value = @traitval, cur_value = @traitval, text_value = '' where trait = @traitid;