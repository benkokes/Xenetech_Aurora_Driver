// Per-job settings persistence for the Aurora custom Properties window.
// No file, registry, network, user-property-bag or queue-property-bag access.
var auroraPsf = "http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework";
var auroraPrivate = "urn:aurora-jobserver:print-schema:1";
var auroraParameter = "JobAuroraPreferences";
var auroraBagKey = "AuroraPreferencesPayload";

function auroraDocument(schema) {
    var document = schema.XmlNode;
    if (!document.documentElement) throw new Error("Expected a Print Schema document.");
    document.setProperty("SelectionLanguage", "XPath");
    document.setProperty("SelectionNamespaces", "xmlns:psf='" + auroraPsf + "'");
    return document;
}
function auroraNamed(document, tag) {
    return document.documentElement.selectNodes("psf:" + tag +
        "[substring-after(@name, ':')='" + auroraParameter + "']" +
        "[namespace::*[name()=substring-before(../@name, ':') and .='" + auroraPrivate + "']]");
}
function auroraCheckPayload(value) {
    if (typeof value !== "string" || value.length > 20000 ||
        (value.length !== 0 && (value.length % 4 !== 0 || !/^[A-Za-z0-9+/]+={0,2}$/.test(value))))
        throw new Error("Invalid Aurora settings payload.");
    return value;
}
function auroraRead(schema) {
    var document = auroraDocument(schema), nodes = auroraNamed(document, "ParameterInit");
    if (nodes.length > 1) throw new Error("Duplicate Aurora settings.");
    if (nodes.length === 0) return "";
    var values = nodes.item(0).selectNodes("psf:Value");
    if (values.length !== 1 || nodes.item(0).childNodes.length !== 1)
        throw new Error("Malformed Aurora settings parameter.");
    return auroraCheckPayload(values.item(0).text);
}
function auroraElement(document, name) {return document.createNode(1, "psf:" + name, auroraPsf);}
function auroraNamespaces(root) {
    var namespaces = [["auroraSettings", auroraPrivate], ["xsi", "http://www.w3.org/2001/XMLSchema-instance"],
        ["xsd", "http://www.w3.org/2001/XMLSchema"], ["psk", "http://schemas.microsoft.com/windows/2003/08/printing/printschemakeywords"]];
    for (var i = 0; i < namespaces.length; i++) {
        var name = "xmlns:" + namespaces[i][0], existing = root.getAttribute(name);
        if (!existing) root.setAttribute(name, namespaces[i][1]);
        else if (existing !== namespaces[i][1]) throw new Error("Conflicting Print Schema namespace.");
    }
}
function auroraValue(document, type, value) {
    var node = auroraElement(document, "Value");
    var attribute = document.createNode(2, "xsi:type", "http://www.w3.org/2001/XMLSchema-instance");
    attribute.text = "xsd:" + type;node.attributes.setNamedItem(attribute);node.text = value;return node;
}
function auroraWrite(schema, payload) {
    payload = auroraCheckPayload(payload);
    var document = auroraDocument(schema), nodes = auroraNamed(document, "ParameterInit"), root = document.documentElement;
    if (nodes.length > 1) throw new Error("Duplicate Aurora settings.");
    while (nodes.length) {root.removeChild(nodes.item(0));nodes = auroraNamed(document, "ParameterInit");}
    if (payload.length === 0) return;
    auroraNamespaces(root);
    var parameter = auroraElement(document, "ParameterInit");
    parameter.setAttribute("name", "auroraSettings:" + auroraParameter);
    parameter.appendChild(auroraValue(document, "string", payload));root.appendChild(parameter);
}
function completePrintCapabilities(printTicket, scriptContext, printCapabilities) {
    var document = auroraDocument(printCapabilities), root = document.documentElement;
    if (auroraNamed(document, "ParameterDef").length) return;
    auroraNamespaces(root);
    var parameter = auroraElement(document, "ParameterDef");
    parameter.setAttribute("name", "auroraSettings:" + auroraParameter);
    var properties = [["DataType", "QName", "xsd:string"], ["DefaultValue", "string", ""],
        ["MinLength", "integer", "0"], ["MaxLength", "integer", "20000"],
        ["Mandatory", "QName", "psk:Optional"], ["UnitType", "string", "base64 UTF-8 settings snapshot"]];
    for (var i = 0; i < properties.length; i++) {
        var property = auroraElement(document, "Property");
        property.setAttribute("name", "psf:" + properties[i][0]);
        property.appendChild(auroraValue(document, properties[i][1], properties[i][2]));parameter.appendChild(property);
    }
    root.appendChild(parameter);
}
function validatePrintTicket(printTicket, scriptContext) {
    try {auroraRead(printTicket);return 1;} catch (error) {return 0;}
}
function convertPrintTicketToDevMode(printTicket, scriptContext, devModeProperties) {
    // Empty explicitly clears a previous full-settings snapshot.
    devModeProperties.SetString(auroraBagKey, auroraRead(printTicket));
}
function convertDevModeToPrintTicket(devModeProperties, scriptContext, printTicket) {
    // The map declares this property even for older, empty DEVMODEs. A failed
    // bag read must propagate; silently falling back could discard job settings.
    auroraWrite(printTicket, devModeProperties.GetString(auroraBagKey));
}
