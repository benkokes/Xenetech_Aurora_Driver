using System;
using System.IO;
using PrinterExtensionLib;

namespace Aurora.Frontend
{
    public static class NativePreferencesSessionTests
    {
        sealed class Operation : PrintSchemaAsyncOperation
        {
            public IPrintSchemaTicket Ticket;
            public int Status;
            public event IPrintSchemaAsyncOperationEvent_CompletedEventHandler Completed;
            public void Start() {if(Completed!=null) Completed(Ticket,Status);}
            public void Cancel() { }
        }
        sealed class Caps : IPrintSchemaCapabilities
        {
            public object Document;
            public object XmlNode {get {return Document;}}
            public string Name {get {return "PrintCapabilities";}}
            public string NamespaceUri {get {return ClassicTicket.Framework;}}
            public IPrintSchemaFeature GetFeatureByKeyName(string key) {throw new InvalidOperationException("Feature wrappers must not be used.");}
            public IPrintSchemaFeature GetFeature(string name,string ns) {throw new InvalidOperationException("Feature wrappers must not be used.");}
            public IPrintSchemaPageImageableSize PageImageableSize {get {return null;}}
            public uint JobCopiesAllDocumentsMinValue {get {return 1;}}
            public uint JobCopiesAllDocumentsMaxValue {get {return 1;}}
            public IPrintSchemaOption GetSelectedOptionInPrintTicket(IPrintSchemaFeature feature) {throw new NotSupportedException();}
            public IPrintSchemaOptionCollection GetOptions(IPrintSchemaFeature feature) {throw new NotSupportedException();}
        }
        sealed class Ticket : IPrintSchemaTicket
        {
            public object Document;
            public Caps Capabilities;
            public int Notifications,Commits;
            public bool NullOperation,NullValidated,FailValidation,NullCommit,FailCommit;
            public string CommittedXml;
            public object XmlNode {get {return Document;}}
            public string Name {get {return "PrintTicket";}}
            public string NamespaceUri {get {return ClassicTicket.Framework;}}
            public uint JobCopiesAllDocuments {get;set;}
            public IPrintSchemaFeature GetFeatureByKeyName(string key) {throw new InvalidOperationException("Feature wrappers are unavailable after XML edits.");}
            public IPrintSchemaFeature GetFeature(string name,string ns) {throw new InvalidOperationException("Feature wrappers are unavailable after XML edits.");}
            public IPrintSchemaCapabilities GetCapabilities() {return Capabilities;}
            public void NotifyXmlChanged() {Notifications++;}
            public void ValidateAsync(out PrintSchemaAsyncOperation operation)
            {operation=NullOperation?null:new Operation {Ticket=NullValidated?null:new Ticket {Document=Dom((string)((dynamic)Document).xml),Capabilities=Capabilities},Status=FailValidation?unchecked((int)0x80004005):0};}
            public void CommitAsync(IPrintSchemaTicket ticket,out PrintSchemaAsyncOperation operation)
            {Commits++;CommittedXml=(string)((dynamic)ticket.XmlNode).xml;operation=NullCommit?null:new Operation {Ticket=ticket,Status=FailCommit?unchecked((int)0x80004005):0};}
        }
        sealed class Request : IPrinterExtensionRequest
        {
            public int Completed,Canceled,CancelStatus;
            public void Complete() {Completed++;}
            public void Cancel(int status,string message) {Canceled++;CancelStatus=status;}
        }
        sealed class Context : IPrinterExtensionEventArgs
        {
            public Ticket Ticket;
            public Request Pending=new Request();
            public PrinterQueue PrinterQueue {get {return null;}}
            public IPrintSchemaTicket PrintSchemaTicket {get {return Ticket;}}
            public IPrinterPropertyBag DriverProperties {get {return null;}}
            public IPrinterPropertyBag UserProperties {get {return null;}}
            public string BidiNotification {get {return "";}}
            public Guid ReasonId {get {return Guid.Empty;}}
            public IPrinterExtensionRequest Request {get {return Pending;}}
            public string SourceApplication {get {return "Aurora save regression";}}
            public Guid DetailedReasonId {get {return Guid.Empty;}}
            public int WindowModal {get {return 0;}}
            public IntPtr WindowParent {get {return IntPtr.Zero;}}
        }
        static object Dom(string xml)
        {dynamic doc=Activator.CreateInstance(Type.GetTypeFromProgID("Msxml2.DOMDocument.6.0"));doc.async=false;if(!(bool)doc.loadXML(xml)) throw new InvalidDataException("Invalid test XML.");return doc;}
        static Context Create(string root)
        {return new Context {Ticket=new Ticket {Document=Dom(File.ReadAllText(Path.Combine(root,"default-printticket.xml"))),Capabilities=new Caps {Document=Dom(File.ReadAllText(Path.Combine(root,"printcapabilities.xml")))}}};}
        static void Check(bool value,string message) {if(!value) throw new InvalidOperationException(message);}
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                Context context=Create(args[0]);NativePreferencesSession session=new NativePreferencesSession(context,action=>action());
                Check(session.SupportsFullSettings && session.FullSettings.Resolution==167,"Native initial settings missing.");
                ClassicSettings selected=session.FullSettings;selected.RasterPower=46.25M;selected.VectorPower=16.25M;selected.VectorPpi=777;
                bool saved=false;string failed=null;
                session.SaveFull(selected,()=>saved=true,message=>failed=message);
                Check(saved && failed==null && context.Ticket.Notifications==1 && context.Ticket.Commits==1,"Full save failed after feature-wrapper invalidation.");
                Check(ClassicTicket.Read(context.Ticket.CommittedXml,ClassicTicket.Selection(context.Ticket.CommittedXml)).ToXml()==selected.ToXml(),"Commit lost chosen settings.");
                session.Complete();session.Complete();Check(context.Pending.Completed==1,"Request completed more than once.");
                Console.WriteLine("PASS full Save/Validate/Commit without feature-wrapper lookups after XML mutation");
                for(int i=0;i<5;i++)
                {
                    context=Create(args[0]);context.Ticket.NullOperation=i==0;context.Ticket.NullValidated=i==1;context.Ticket.FailValidation=i==2;context.Ticket.NullCommit=i==3;context.Ticket.FailCommit=i==4;
                    session=new NativePreferencesSession(context,action=>action());saved=false;failed=null;
                    try {session.SaveFull(new ClassicSettings(),()=>saved=true,message=>failed=message);} catch(InvalidOperationException error) {failed=error.Message;}
                    Check(!saved && !String.IsNullOrEmpty(failed) && !failed.Contains("Object reference"),"Native failure was not reported clearly.");
                    if(i<3) Check(context.Ticket.Commits==0,"Invalid settings were committed.");
                    session.Cancel();session.Complete();Check(context.Pending.Canceled==1 && context.Pending.CancelStatus==1 && context.Pending.Completed==0,"Cancel did not preserve the caller's request.");
                }
                Console.WriteLine("PASS five missing-operation/failed-validation/failed-commit paths, with safe Cancel");
                return 0;
            }
            catch(Exception error) {Console.Error.WriteLine(error);return 1;}
        }
    }
}
