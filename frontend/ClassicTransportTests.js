// Windows Script Host + real MSXML tests; no spooler changes or device I/O.
var shell = new ActiveXObject("Scripting.FileSystemObject");
var script = shell.OpenTextFile(WScript.Arguments(0), 1);
eval(script.ReadAll());script.Close();
var tests = 0;
function check(condition, message) {if (!condition) throw new Error(message);}
function schema(root) {
    var doc = new ActiveXObject("Msxml2.DOMDocument.6.0");doc.async = false;
    doc.loadXML('<psf:' + root + ' xmlns:psf="' + auroraPsf + '" version="1"/>');return {XmlNode:doc};
}
function bag() {return {value:"",SetString:function(key,value){check(key===auroraBagKey,"Wrong bag key");this.value=value;},GetString:function(key){check(key===auroraBagKey,"Wrong bag key");return this.value;}};}
function run(name, action) {action();tests++;WScript.Echo("PASS " + name);}
run("complete capability definition is idempotent", function() {
    var cap = schema("PrintCapabilities");completePrintCapabilities(null,null,cap);completePrintCapabilities(null,null,cap);
    check(auroraNamed(cap.XmlNode,"ParameterDef").length===1,"Duplicate capability definition");
    check(cap.XmlNode.documentElement.selectNodes("psf:ParameterDef/psf:Property").length===6,"Missing parameter properties");
    check(cap.XmlNode.documentElement.selectSingleNode("psf:ParameterDef/psf:Property/psf:Value").attributes.getNamedItem("xsi:type").namespaceURI==="http://www.w3.org/2001/XMLSchema-instance","Type attribute lost its namespace");
});
run("namespace aliases on root and parameter preserve the same payload", function() {
    var ticket=schema("PrintTicket");ticket.XmlNode.documentElement.setAttribute("xmlns:other",auroraPrivate);
    auroraWrite(ticket,"QUJDRA==");check(auroraRead(ticket)==="QUJDRA==","Second namespace alias hid the parameter");
    var node=auroraNamed(ticket.XmlNode,"ParameterInit").item(0);
    node.setAttribute("xmlns:local",auroraPrivate);node.setAttribute("name","local:"+auroraParameter);
    check(auroraRead(ticket)==="QUJDRA==","Local namespace alias hid the parameter");
});
run("private DEVMODE roundtrip preserves independent job snapshots", function() {
    var a=schema("PrintTicket"), b=schema("PrintTicket"), store=bag();
    auroraWrite(a,"QUJDRA==");convertPrintTicketToDevMode(a,null,store);
    auroraWrite(a,"Rk9P");convertDevModeToPrintTicket(store,null,b);
    check(auroraRead(b)==="QUJDRA==" && auroraRead(a)==="Rk9P","Jobs share mutable settings");
    check(validatePrintTicket(b,null)===1,"Valid payload rejected");
});
run("empty legacy ticket clears the former snapshot", function() {
    var ticket=schema("PrintTicket"), store=bag();store.value="QUJDRA==";
    convertPrintTicketToDevMode(ticket,null,store);check(store.value==="","Old settings survived reset");
    auroraWrite(ticket,"QUJDRA==");convertDevModeToPrintTicket(store,null,ticket);check(auroraRead(ticket)==="","Ticket kept stale settings");
});
run("malformed duplicate and oversized snapshots are rejected", function() {
    var ticket=schema("PrintTicket");auroraWrite(ticket,"QUJDRA==");
    var root=ticket.XmlNode.documentElement;root.appendChild(root.firstChild.cloneNode(true));
    check(validatePrintTicket(ticket,null)===0,"Duplicate accepted");
    for(var i=0;i<3;i++) {
        var payload=i===0?"bad!":i===1?"ABC":new Array(20005).join("A"), rejected=false;
        try {auroraWrite(schema("PrintTicket"),payload);} catch(error) {rejected=true;}
        check(rejected,"Malformed payload accepted");
    }
});
WScript.Echo(tests + " MSXML settings transport checks passed.");
