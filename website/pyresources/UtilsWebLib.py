import web, time, sys, traceback, json
from wsgilog import WsgiLog


MUST_NOT = 0
MAY = 1
MUST = 2

DEFAULT_PROPERTIES = {'allow_unsafe': 0}
DEFAULT_INPUT_ACCEPT = {None: (MUST_NOT, str)}
# None: (MUST_NOT, anytype) denies everything not covered by the other directives
# None: (MAY, str) accepts everything not covered by the other directives

http_status_map = {
    401: "401 Unauthorized",
    400: "400 Bad Request",
    500: "500 Internal Server Error"
    }

class WebException(Exception):
    def __init__(self, msg, errorcode = 0):
        super(WebException, self).__init__(msg)
        self.code = errorcode

def unvalidated(data):
    return data

def validator_str_maxlen(maxlen):
    def validator(data):
        string = str(data) #data.encode('utf-8')
        if len(string) > maxlen:
            raise WebException("Input too long", 400)
        else:
            return string
    return validator

def validator_str_range(minlen, maxlen):
    def validator(data):
        string = str(data) #data.encode('utf-8')
        if len(string) > maxlen or len(string) < minlen:
            raise WebException("Input not in accepted length range", 400)
        else:
            return string
    return validator

def validator_set(values):
    def validator(data):
        string = str(data) #data.encode('utf-8')
        if not string in values:
            raise WebException("Illegal value", 400)
        else:
            return string
    return validator

def validator_positive_integer(value):
    retval = int(value)
    if retval < 0:
        raise WebException("Integer must be positive", 400)
    else:
        return retval

class WebResponse:
    def __init__(self, config, session, properties = {}, accepted_input = {}, min_access_level = 0):
        self.config = config
        self.accepted_params = DEFAULT_INPUT_ACCEPT.copy()
        self.accepted_params.update(accepted_input)
        self.props = DEFAULT_PROPERTIES.copy()
        self.props.update(properties)
        self.session = session
        self.min_access_level = min_access_level
        self.timings = []
        self.logger = web.ctx.env.get('wsgilog.logger')
        self.input_data = {}
        self.logger.info("WebResponse Class instantiated")
    def validateInput(self, raw):
        final_input = {}
        null_directive = self.accepted_params[None]
        for key in raw: # check all inputs for a validator directive
            if key in self.accepted_params:
                directive = self.accepted_params[key]
                if directive[0] != MUST_NOT:
                    try:
                        final_input[key] = directive[1](raw[key]) # if the validator fails, it aborts the entire request into an error
                    except WebException as e:
                        raise WebException("Invalid parameter: "+str(key)+" - "+ str(e), 400)
                    except Exception as e:
                        raise WebException("Failed validation of: "+str(key)+" - "+ str(e), 400)
                else:
                    raise WebException("Illegal parameter: "+str(key), 400)
            else:
                if null_directive[0] != MUST_NOT:
                    final_input[key] = null_directive[1](raw[key])
                else:
                    raise WebException("Illegal parameter: "+str(key), 400)
        # now every parameter has a rule that covers them, check for MUST
        for key in self.accepted_params:
            directive = self.accepted_params[key]
            if directive[0] == MUST and not key in final_input:
                raise WebException("Missing parameter: "+str(key), 400)
            if directive[0] == MAY and not key in final_input:
                final_input[key] = None # init as empty do that we don't check for existence but fot None
        return final_input            
    def preHook(self):
        return
    def postHook(self, result):
        return result
    def getOutputSafeInputData(self):
        o = self.input_data.copy()
        #if o.has_key("token_id"):
        #    o['token_id'] = "[REDACTED]"
        return o
    def request(self, rtype):
        self.timings.append(time.perf_counter())
        web.header('Content-Type', 'text/plain')
        input_data_raw = web.input()
        try:
            if web.ctx.protocol != 'https' and not self.props['allow_unsafe']:
                raise WebException("Use https!")
            if self.min_access_level > self.session.access_level:
                raise WebException("Access Denied!", 401)
            self.input_data = self.validateInput(input_data_raw)
            result = ""
            self.preHook()
            if rtype == "GET":
                result = self.postHook(self.mGET())
            elif rtype == "POST":
                result = self.postHook(self.mPOST())
        except WebException as e:
            self.logger.warning("Error in request of "+web.ctx.path+" from "+str(web.ctx.ip)+" with (raw) parameters: "+str(input_data_raw)+". error: "+str(type(e))+" - "+str(e)+". Error code: "+str(e.code))
            if e.code != 0:
                try:
                    web.ctx.status = http_status_map[e.code]
                except:
                    self.logger.warning("Invalid error status: "+str(e.code))
            sendback = str(e)
            result = self.postHook(sendback)
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.error("Unhandled Exception: "+str(exc_value)+ "\n"+"".join(traceback.format_tb(exc_traceback)))
            web.ctx.status = http_status_map[500]
            sendback = str(exc_value)
            sendback = "Unhandled exception: "+sendback
            result = self.postHook(sendback)
        self.timings.append(time.perf_counter())
        #result["debug"].append({"time": int(1000*(self.timings[1]-self.timings[0]))})
        return result
    def GET(self):
        result = self.request("GET")
        return result
    def POST(self):
        result = self.request("POST")
        return result
    def mGET(self):
        raise WebException('HTTP METHOD NOT AVAILABLE')
    def mPOST(self):
        raise WebException('HTTP METHOD NOT AVAILABLE')

class WebPageResponse(WebResponse):
    def __init__(self, config, session, properties = {}, accepted_input = {}, min_access_level = 0):
        super(WebPageResponse, self).__init__(config, session, properties, accepted_input, min_access_level)
    def postHook(self, result):
        web.header('Content-Type', 'text/html')
        return super(WebPageResponse, self).postHook(result)

class APIResponse(WebResponse):
    def __init__(self, config, session, properties = {}, accepted_input = {}, min_access_level = 0):
        super(APIResponse, self).__init__(config, session, properties, accepted_input, min_access_level)
    def postHook(self, result):
        web.header('Content-Type', 'application/json')
        return json.dumps(super(APIResponse, self).postHook(result))


   

