using System;
using System.Collections.Generic;
using System.IO;
using System.Printing;
using System.Printing.Interop;
using System.Text;
using System.Xml;

namespace Aurora.Frontend
{
    // Read-only provider calls: no queue commit, document printing or device I/O.
    public static class ClassicNativeRoundtrip
    {
        sealed class Sample
        {
            public string Name;public ClassicSettings Settings;
            public Sample(string name,ClassicSettings settings) {Name=name;Settings=settings;}
        }
        static void Field(List<Sample> samples,string name,params object[] values)
        {
            foreach(object value in values)
            {
                ClassicSettings selected=new ClassicSettings();
                typeof(ClassicSettings).GetField(name).SetValue(selected,value);
                selected.Validate();samples.Add(new Sample(name+"="+value,selected));
            }
        }
        static List<Sample> Samples(bool matrix)
        {
            List<Sample> samples=new List<Sample> {
                new Sample("default",new ClassicSettings()),new Sample("powers46-16",new ClassicSettings {RasterPower=46,VectorPower=16}),
                new Sample("fractional-process",new ClassicSettings {RasterPower=45.25M,RasterSpeed=12.345M,VectorSpeed=5.125M,VectorPpi=777}),
                new Sample("combined-unverified",new ClassicSettings {Resolution=500,UseColors=true,Mirror=true,Focus=ClassicFocus.Thickness,ThicknessInches=.125M,Orientation=ClassicOrientation.Left90,Output=ClassicOutput.VectorOnly}),
                new Sample("raster-only",new ClassicSettings {Output=ClassicOutput.RasterOnly}),new Sample("vector-only",new ClassicSettings {Output=ClassicOutput.VectorOnly}),
                new Sample("legacy-held-travel",new ClassicSettings {Version=1,TravelSpeed=90}),
                new Sample("travel-1ips-held",new ClassicSettings {TravelSpeed=1})};
            if(!matrix) return samples;
            foreach(var field in typeof(ClassicSettings).GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance))
            {
                if(field.FieldType==typeof(bool)) Field(samples,field.Name,false,true);
                else if(field.FieldType.IsEnum)
                    foreach(object value in Enum.GetValues(field.FieldType)) Field(samples,field.Name,value);
            }
            Field(samples,"RasterPower",0M,100M,45.25M);Field(samples,"VectorPower",0M,100M,15.75M);
            Field(samples,"RasterSpeed",.001M,31M,150M,12.345M);Field(samples,"VectorSpeed",.001M,15M,1.234M);
            Field(samples,"TravelSpeed",.001M,250M,99.999M);Field(samples,"ThicknessInches",0M,18M,.123456M);
            Field(samples,"PlateWidthInches",.001M,30M,12.345678M);Field(samples,"PlateHeightInches",.001M,18M,9.876543M);
            Field(samples,"OffsetXInches",-30M,30M,-.123456M);Field(samples,"OffsetYInches",-18M,18M,.123456M);
            Field(samples,"VectorPpi",5,999,1000);foreach(int dpi in ClassicSettings.Resolutions) Field(samples,"Resolution",dpi);
            Field(samples,"ContrastLow",0,254);Field(samples,"ContrastHigh",1,255);Field(samples,"ContrastColors",2,256);
            Field(samples,"OutputDirectory","JobServer archive",new string('x',512),"C:\\测试\\jobs");
            Field(samples,"ColorProfile",new string('c',64),new string('测',64));
            for(int index=0;index<16;index++)
            {
                ClassicSettings selected=new ClassicSettings();selected.Colors[index].Enabled=false;
                selected.Colors[index].PowerPercent=12.34M;selected.Colors[index].SpeedIps=1.234M;selected.Colors[index].Ppi=5;
                samples.Add(new Sample("color-"+index+"-disabled-fractional",selected));
            }
            ClassicSettings maximum=new ClassicSettings {OutputDirectory=new string('x',512),ColorProfile=new string('测',64)};
            foreach(ClassicColor c in maximum.Colors) {c.PowerPercent=99.99M;c.SpeedIps=149.999M;c.Ppi=999;}
            samples.Add(new Sample("long-payload-and-colors",maximum));
            return samples;
        }
        static string Xml(PrintTicket ticket) {using(Stream stream=ticket.GetXmlStream()) using(StreamReader reader=new StreamReader(stream)) return reader.ReadToEnd();}
        static XmlDocument Document(string text) {XmlDocument doc=new XmlDocument {XmlResolver=null};using(XmlReader reader=XmlReader.Create(new StringReader(text),new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=1024*1024})) doc.Load(reader);return doc;}
        static bool Named(XmlElement element,string local)
        {string[] value=element.GetAttribute("name").Split(':');return value.Length==2 && value[1]==local && element.GetNamespaceOfPrefix(value[0])==ClassicTicket.Private;}
        static string Snapshot(string xml,ClassicSettings settings)
        {
            dynamic native=Activator.CreateInstance(Type.GetTypeFromProgID("Msxml2.DOMDocument.6.0"));native.async=false;
            if(!(bool)native.loadXML(xml)) throw new InvalidDataException("Could not construct native test document.");
            ClassicTicket.WriteFullNative(native,settings);return (string)native.xml;
        }
        static void Verify(string xml,ClassicSettings expected)
        {
            if(ClassicTicket.Payload(xml)!=expected.ToPayload()) throw new InvalidDataException("Windows lost or changed the complete job preferences.");
            XmlDocument doc=Document(xml);Dictionary<string,string> selected=new Dictionary<string,string>();
            foreach(XmlNode item in doc.DocumentElement.ChildNodes)
            {
                XmlElement feature=item as XmlElement;if(feature==null || feature.NamespaceURI!=ClassicTicket.Framework || feature.LocalName!="Feature") continue;
                foreach(string key in ClassicTicket.Carriers(expected).Keys)
                    if(Named(feature,"Job"+key))
                    {
                        XmlElement option=(XmlElement)feature.GetElementsByTagName("Option",ClassicTicket.Framework)[0];string[] name=option.GetAttribute("name").Split(':');
                        if(name.Length!=2 || option.GetNamespaceOfPrefix(name[0])!=ClassicTicket.Private) throw new InvalidDataException("Changed option namespace.");
                        selected.Add(key,name[1]);
                    }
            }
            if(ClassicTicket.Read(xml,selected).ToXml()!=expected.ToXml()) throw new InvalidDataException("Settings roundtrip changed values.");
        }
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if((args.Length!=1 && (args.Length!=2 || args[1]!="--matrix")) || Directory.Exists(args[0])) throw new ArgumentException("Pass a new report directory and optional --matrix.");
                string output=Path.GetFullPath(args[0]);Directory.CreateDirectory(output);
                const string printer="Aurora JobServer (Test Capture)";
                using(LocalPrintServer server=new LocalPrintServer())
                using(PrintQueue queue=server.GetPrintQueue(printer))
                using(PrintTicketConverter converter=new PrintTicketConverter(printer,1))
                {
                    using(Stream source=queue.GetPrintCapabilitiesAsXml())
                    using(StreamReader reader=new StreamReader(source))
                    {
                        string caps=reader.ReadToEnd();File.WriteAllText(Path.Combine(output,"capabilities.xml"),caps);
                        if(!caps.Contains(ClassicTicket.Parameter)) throw new InvalidOperationException("Installed driver does not yet advertise the full-settings parameter.");
                    }
                    PrintTicket defaultTicket=queue.DefaultPrintTicket;
                    if(defaultTicket==null) throw new InvalidOperationException("The installed provider did not generate a default PrintTicket.");
                    string baseline=Xml(defaultTicket);
                    PrintTicket userBefore=queue.UserPrintTicket;string userBaseline=userBefore==null?null:Xml(userBefore);
                    List<Sample> samples=Samples(args.Length==2);
                    StringBuilder manifest=new StringBuilder("index\tcase\tpayload_characters\tdevmode_bytes\r\n");
                    byte[][] modes=new byte[samples.Count][];
                    for(int i=0;i<samples.Count;i++)
                    {
                        ClassicSettings selected=samples[i].Settings;
                        string requested=Snapshot(baseline,selected);
                        using(MemoryStream stream=new MemoryStream(Encoding.UTF8.GetBytes(requested)))
                        {
                            PrintTicket delta=new PrintTicket(stream);
                            PrintTicket validated=queue.MergeAndValidatePrintTicket(queue.DefaultPrintTicket,delta,PrintTicketScope.JobScope).ValidatedPrintTicket;
                            Verify(Xml(validated),selected);modes[i]=converter.ConvertPrintTicketToDevMode(validated,BaseDevModeType.PrinterDefault);
                            File.WriteAllText(Path.Combine(output,"validated-"+i+".xml"),Xml(validated));
                            File.WriteAllText(Path.Combine(output,"expected-"+i+".xml"),selected.ToXml());
                            manifest.Append(i).Append('\t').Append(samples[i].Name).Append('\t').Append(selected.ToPayload().Length).Append('\t').Append(modes[i].Length).Append("\r\n");
                        }
                    }
                    for(int i=modes.Length-1;i>=0;i--)
                    {
                        PrintTicket restored=converter.ConvertDevModeToPrintTicket(modes[i]);Verify(Xml(restored),samples[i].Settings);
                        File.WriteAllText(Path.Combine(output,"restored-"+i+".xml"),Xml(restored));
                        Console.WriteLine("PASS native snapshot "+i+" "+samples[i].Name+"; DEVMODE bytes "+modes[i].Length);
                    }
                    if(Xml(queue.DefaultPrintTicket)!=baseline) throw new InvalidOperationException("The queue defaults changed unexpectedly.");
                    PrintTicket userAfter=queue.UserPrintTicket;
                    if((userAfter==null?null:Xml(userAfter))!=userBaseline) throw new InvalidOperationException("User printer defaults changed unexpectedly.");
                    File.WriteAllText(Path.Combine(output,"cases.tsv"),manifest.ToString());
                    File.WriteAllText(Path.Combine(output,"result.txt"),"PASS: "+samples.Count+" independent full snapshots survived native validation and DEVMODE roundtrip. Queue and user defaults unchanged; no print submitted.\r\n");
                }
                return 0;
            }
            catch(Exception error) {Console.Error.WriteLine(error);return 1;}
        }
    }
}
