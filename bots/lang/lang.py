import os, json

class LangException(Exception): # use this for 'known' error situations
    def __init__(self, msg):
        super(LangException, self).__init__(msg)
        
class LanguageStringProvider():
    def __init__(self, lang_dir = os.path.abspath(__file__)):
        self.languages = {}
        for fn in os.listdir(lang_dir):
            if fn.endswith(".json"):
                langname = fn[:-5]
                try:
                    print(f"Loading language {langname} from  {fn}")
                    with open(os.path.join(lang_dir, fn), "r", encoding="utf-8") as f: # website breaks without explicit encoding
                        self.languages[langname] = json.loads(f.read())
                except json.decoder.JSONDecodeError:
                    print(f"Failed loading {langname}")
    def get(self, lang_id, string_name, *args):
        try:
            return self.languages[lang_id][string_name].format(*args)
        except KeyError:
            if string_name in self.languages[lang_id]: # this happens when the lang string contains "{something}" instead of "{}", that breaks the call to str.format
                raise LangException(f'Someone wrote a bad language string! language: {lang_id}, langstring: {string_name}, contents: {self.languages[lang_id][string_name]}, arguments: {args}')
            else:
                print(f"Missing string {string_name} for language {lang_id}")
                return string_name.format(*args)
        except IndexError:
            raise LangException(f'Broken text parameters for {string_name}: "{self.languages[lang_id][string_name]}", language {lang_id}, parameters "{args}"')
    def formatException(self, lang_id, exception):
        return self.get(lang_id, exception.args[1], *exception.args[2])
        

if __name__ == "__main__":
    lp = LanguageStringProvider(".")
    #print(lp.get("ITA", "test_args", 1, 2, "3"))
    
