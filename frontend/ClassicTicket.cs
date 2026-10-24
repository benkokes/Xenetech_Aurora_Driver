using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Xml;

namespace Aurora.Frontend
{
    public static class ClassicTicket
    {
        public const string Framework="http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework";
        public const string Private="urn:aurora-jobserver:print-schema:1";
        public const string Parameter="JobAuroraPreferences";
        static readonly string[] Speeds={"Speed1","Speed10","Speed100","Speed500","Speed1000","Speed2000","Speed3000","Speed5000","Speed8000","Speed10000","Speed15000","Speed20000","Speed25000","Speed30000","Speed31000"};
        static readonly int[] Ppis={5,10,50,100,200,250,500,750,1000};
        static string DecimalOption(string prefix,decimal value,decimal scale)
        {decimal scaled=value*scale;return scaled==Decimal.Truncate(scaled)?prefix+scaled.ToString("0",CultureInfo.InvariantCulture):"Custom";}
        static string Speed(decimal value) {string option=DecimalOption("Speed",value,1000);return Array.IndexOf(Speeds,option)>=0?option:"Custom";}
        public static Dictionary<string,string> Carriers(ClassicSettings s)
        {
            s.Validate();
            return new Dictionary<string,string> {
                {"AuroraRasterPower",DecimalOption("Percent",s.RasterPower,1)},
                {"AuroraRasterSpeed",Speed(s.RasterSpeed)},
                {"AuroraVectorPower",DecimalOption("Percent",s.VectorPower,1)},
                {"AuroraVectorSpeed",Speed(s.VectorSpeed)},
                {"AuroraVectorPPI",Array.IndexOf(Ppis,s.VectorPpi)>=0?"PPI"+s.VectorPpi:"Custom"},
                {"AuroraLaserDPI",s.Resolution==100 || s.Resolution==167?"DPI"+s.Resolution:"Custom"},
                {"AuroraAutostart",s.Autostart?"On":"Off"},
                {"AuroraOutputMode",s.Output==ClassicOutput.RasterAndVector?"RasterAndVector":"Custom"},
                {"AuroraFocus",s.Focus==ClassicFocus.None?"None":"Custom"}
            };
        }
        static XmlDocument Document(string xml)
        {
            XmlDocument document=new XmlDocument {XmlResolver=null};
            using(XmlReader input=XmlReader.Create(new StringReader(xml),new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=1024*1024})) document.Load(input);
            if(document.DocumentElement.LocalName!="PrintTicket" || document.DocumentElement.NamespaceURI!=Framework || document.DocumentElement.GetAttribute("version")!="1") throw new InvalidDataException("Expected a version-1 PrintTicket.");
            return document;
        }
        static bool Named(XmlElement node,string local)
        {
            string[] name=node.GetAttribute("name").Split(':');
            return name.Length==2 && name[1]==local && node.GetNamespaceOfPrefix(name[0])==Private;
        }
        public static Dictionary<string,string> Selection(string xml)
        {
            XmlDocument document=Document(xml);Dictionary<string,string> result=new Dictionary<string,string>();
            string[] keys={"AuroraRasterPower","AuroraRasterSpeed","AuroraVectorPower","AuroraVectorSpeed","AuroraVectorPPI","AuroraLaserDPI","AuroraAutostart","AuroraOutputMode","AuroraFocus"};
            foreach(XmlNode item in document.GetElementsByTagName("Feature",Framework))
            {
                XmlElement feature=(XmlElement)item;
                foreach(string key in keys)
                {
                    if(!Named(feature,"Job"+key)) continue;
                    if(feature.ParentNode!=document.DocumentElement || result.ContainsKey(key)) throw new InvalidDataException("Nested or duplicate laser feature: "+key);
                    XmlNodeList options=feature.GetElementsByTagName("Option",Framework);
                    if(options.Count!=1 || options[0].ParentNode!=feature) throw new InvalidDataException("Expected one laser option: "+key);
                    XmlElement option=(XmlElement)options[0];string[] name=option.GetAttribute("name").Split(':');
                    if(name.Length!=2 || option.GetNamespaceOfPrefix(name[0])!=Private) throw new InvalidDataException("Unexpected laser option namespace: "+key);
                    result.Add(key,name[1]);
                }
            }
            if(result.Count!=keys.Length) throw new InvalidDataException("Incomplete laser feature selection.");
            return result;
        }
        public static string Payload(string xml)
        {
            XmlDocument document=Document(xml);string result=null;
            foreach(XmlNode item in document.GetElementsByTagName("ParameterInit",Framework))
            {
                XmlElement element=(XmlElement)item;if(!Named(element,Parameter)) continue;
                if(element.ParentNode!=document.DocumentElement || result!=null) throw new InvalidDataException("Nested or duplicate Aurora settings.");
                XmlNodeList values=element.GetElementsByTagName("Value",Framework);
                if(values.Count!=1 || values[0].ParentNode!=element || element.ChildNodes.Count!=1) throw new InvalidDataException("Malformed Aurora settings parameter.");
                result=values[0].InnerText;if(result.Length!=0) ClassicSettings.FromPayload(result);
            }
            return result;
        }
        public static ClassicSettings Read(string xml,Dictionary<string,string> selection)
        {
            string payload=Payload(xml);ClassicSettings settings;
            if(!String.IsNullOrEmpty(payload)) settings=ClassicSettings.FromPayload(payload);
            else
            {
                settings=new ClassicSettings();
                try
                {
                    settings.RasterPower=Decimal.Parse(selection["AuroraRasterPower"].Substring(7),CultureInfo.InvariantCulture);
                    settings.VectorPower=Decimal.Parse(selection["AuroraVectorPower"].Substring(7),CultureInfo.InvariantCulture);
                    settings.RasterSpeed=Decimal.Parse(selection["AuroraRasterSpeed"].Substring(5),CultureInfo.InvariantCulture)/1000;
                    settings.VectorSpeed=Decimal.Parse(selection["AuroraVectorSpeed"].Substring(5),CultureInfo.InvariantCulture)/1000;
                    settings.VectorPpi=Int32.Parse(selection["AuroraVectorPPI"].Substring(3),CultureInfo.InvariantCulture);
                    settings.Resolution=Int32.Parse(selection["AuroraLaserDPI"].Substring(3),CultureInfo.InvariantCulture);
                    settings.Autostart=selection["AuroraAutostart"]=="On";
                }
                catch(Exception error) {throw new InvalidDataException("Full custom settings are missing from this print request.",error);}
            }
            Dictionary<string,string> expected=Carriers(settings);
            foreach(var pair in expected)
                if(!selection.ContainsKey(pair.Key) || selection[pair.Key]!=pair.Value) throw new InvalidDataException("Conflicting laser settings: "+pair.Key);
            return settings;
        }
        // Used with the live MSXML document too: build an isolated fragment first,
        // then load only that parameter into the caller's document.
        public static string ParameterXml(ClassicSettings settings)
        {
            XmlDocument document=new XmlDocument {XmlResolver=null};
            XmlElement parameter=document.CreateElement("psf","ParameterInit",Framework);document.AppendChild(parameter);
            parameter.SetAttribute("xmlns:auroraSettings",Private);
            parameter.SetAttribute("xmlns:xsi","http://www.w3.org/2001/XMLSchema-instance");
            parameter.SetAttribute("xmlns:xsd","http://www.w3.org/2001/XMLSchema");
            parameter.SetAttribute("name","auroraSettings:"+Parameter);
            XmlElement value=document.CreateElement("psf","Value",Framework);
            XmlAttribute type=document.CreateAttribute("xsi","type","http://www.w3.org/2001/XMLSchema-instance");type.Value="xsd:string";value.Attributes.Append(type);
            value.InnerText=settings.ToPayload();parameter.AppendChild(value);return document.OuterXml;
        }
        public static void WriteNative(object nativeDocument,ClassicSettings settings)
        {
            string payload=settings.ToPayload();dynamic document=nativeDocument;
            // Validate existing snapshots and duplicate parameters before mutation.
            Payload((string)document.xml);
            document.setProperty("SelectionLanguage","XPath");
            document.setProperty("SelectionNamespaces","xmlns:psf='"+Framework+"'");
            dynamic root=document.documentElement;
            string privatePrefix=Document((string)document.xml).DocumentElement.GetPrefixOfNamespace(Private);
            if(String.IsNullOrEmpty(privatePrefix)) privatePrefix="auroraSettings";
            foreach(string[] entry in new string[][] {
                new string[]{"psf",Framework},new string[]{privatePrefix,Private},
                new string[]{"xsi","http://www.w3.org/2001/XMLSchema-instance"},new string[]{"xsd","http://www.w3.org/2001/XMLSchema"}})
            {
                string name="xmlns:"+entry[0],current=Convert.ToString((object)root.getAttribute(name),CultureInfo.InvariantCulture);
                if(!String.IsNullOrEmpty(current) && current!=entry[1]) throw new InvalidDataException("Conflicting preference namespace.");
                if(String.IsNullOrEmpty(current)) root.setAttribute(name,entry[1]);
            }
            dynamic nodes=root.selectNodes("psf:ParameterInit[substring-after(@name,':')='"+Parameter+"'][namespace::*[name()=substring-before(../@name,':') and .='"+Private+"']]");
            if((int)nodes.length==1) root.removeChild(nodes.item(0));
            dynamic parameter=document.createNode(1,"psf:ParameterInit",Framework);parameter.setAttribute("name",privatePrefix+":"+Parameter);
            dynamic value=document.createNode(1,"psf:Value",Framework);
            dynamic attribute=document.createNode(2,"xsi:type","http://www.w3.org/2001/XMLSchema-instance");
            attribute.text="xsd:string";value.attributes.setNamedItem(attribute);value.text=payload;
            parameter.appendChild(value);root.appendChild(parameter);
            if(Payload((string)document.xml)!=payload) throw new InvalidDataException("Could not attach complete preferences to the print request.");
        }
        public static void WriteFullNative(object nativeDocument,ClassicSettings settings)
        {
            dynamic document=nativeDocument;
            Selection((string)document.xml); // Reject incomplete/duplicate input before editing.
            WriteNative(nativeDocument,settings);
            dynamic root=document.documentElement;
            foreach(var pair in Carriers(settings))
            {
                dynamic features=root.selectNodes("psf:Feature[substring-after(@name,':')='Job"+pair.Key+"'][namespace::*[name()=substring-before(../@name,':') and .='"+Private+"']]");
                if((int)features.length!=1) throw new InvalidDataException("Laser feature unavailable while saving: "+pair.Key);
                dynamic options=features.item(0).selectNodes("psf:Option");
                if((int)options.length!=1) throw new InvalidDataException("Laser option unavailable while saving: "+pair.Key);
                dynamic option=options.item(0);string previous=(string)option.getAttribute("name");
                option.setAttribute("name",previous.Split(':')[0]+":"+pair.Value);
            }
            string xml=(string)document.xml;
            if(Read(xml,Selection(xml)).ToXml()!=settings.ToXml()) throw new InvalidDataException("The print request did not retain the selected settings.");
        }
    }
}
