using System;
using System.Collections.Generic;
using System.IO;
using System.Windows.Forms;
using PrinterExtensionLib;

namespace Aurora.Frontend
{
    public sealed class NativePreferencesSession : IPreferencesSession
    {
        public const string PrivateNamespace="urn:aurora-jobserver:print-schema:1";
        readonly IPrinterExtensionEventArgs context;
        readonly IPrintSchemaTicket ticket;
        readonly IPrintSchemaCapabilities capabilities;
        readonly Action<Action> onUi;
        readonly PreferenceData data;
        PrintSchemaAsyncOperation validation;
        PrintSchemaAsyncOperation commit;
        bool ended;
        public PreferenceData Data { get { return data; } }
        static string TicketXml(IPrintSchemaTicket ticket) {return (string)((dynamic)ticket.XmlNode).xml;}
        public bool SupportsFullSettings {get {return ((string)((dynamic)capabilities.XmlNode).xml).Contains("JobAuroraPreferences");}}
        public ClassicSettings FullSettings {get {return ClassicTicket.Read(TicketXml(ticket),data.Selected);}}

        public NativePreferencesSession(IPrinterExtensionEventArgs context,Action<Action> onUi)
        {
            this.context=context;
            this.onUi=onUi;
            if(context==null || onUi==null) throw new ArgumentNullException("context");
            ticket=context.PrintSchemaTicket;
            if(ticket==null) throw new InvalidOperationException("Windows did not supply a print request for these preferences.");
            capabilities=ticket.GetCapabilities();
            if(capabilities==null) throw new InvalidOperationException("Windows did not supply this printer's capabilities.");
            data=PreferenceData.ReadXmlText(TicketXml(ticket),(string)((dynamic)capabilities.XmlNode).xml);
            data.Check(data.Selected);
        }

        public void Save(Dictionary<string,string> selection,Action saved,Action<string> failed)
        {Save(selection,null,saved,failed);}
        public void SaveFull(ClassicSettings settings,Action saved,Action<string> failed)
        {
            string stage="preparing complete preferences";
            try
            {
                if(!SupportsFullSettings) throw new InvalidOperationException("This driver does not support complete job preferences yet.");
                if(ended) throw new InvalidOperationException("This settings request is closed.");
                string payload=settings.ToPayload();Dictionary<string,string> selection=ClassicTicket.Carriers(settings);data.Check(selection);
                stage="updating the print request";ClassicTicket.WriteFullNative(ticket.XmlNode,settings);
                stage="refreshing Windows settings";ticket.NotifyXmlChanged();
                stage="starting Windows validation";Save(selection,payload,saved,failed);
            }
            catch(Exception error)
            {PrinterExtensionProgram.Log(new InvalidOperationException("Error "+stage+".",error));throw new InvalidOperationException("Could not save preferences while "+stage+": "+error.Message,error);}
        }
        void Save(Dictionary<string,string> selection,string payload,Action saved,Action<string> failed)
        {
            if(ended) throw new InvalidOperationException("This settings request is closed.");
            data.Check(selection);
            Dictionary<string,string> requested=new Dictionary<string,string>(selection);
            if(payload==null)
                foreach(string key in PreferenceData.Keys)
                {
                    IPrintSchemaFeature feature=ticket.GetFeature("Job"+key,PrivateNamespace),cap=capabilities.GetFeature("Job"+key,PrivateNamespace);
                    if(feature==null || cap==null) throw new InvalidOperationException("Laser feature unavailable: "+key);
                    IPrintSchemaOption option=cap.GetOption(requested[key],PrivateNamespace);
                    if(option==null) throw new InvalidOperationException("Laser option unavailable: "+key);
                    feature.SelectedOption=option;
                }
            ticket.ValidateAsync(out validation);
            if(validation==null) throw new InvalidOperationException("Windows returned no preference-validation operation.");
            validation.Completed += delegate(IPrintSchemaTicket validated,int status) { onUi(delegate {
                try
                {
                    if(status<0) throw new InvalidOperationException("Windows could not validate the laser settings.");
                    if(validated==null) throw new InvalidOperationException("Windows returned no validated print request.");
                    Dictionary<string,string> actual=ClassicTicket.Selection(TicketXml(validated));
                    foreach(string key in PreferenceData.Keys)
                        if(actual[key]!=requested[key])
                            throw new InvalidOperationException("Windows changed a laser setting. Review the values before saving.");
                    if(payload!=null && ClassicTicket.Payload(TicketXml(validated))!=payload)
                        throw new InvalidOperationException("Windows did not preserve the complete preferences. The request was not saved.");
                    ticket.CommitAsync(validated,out commit);
                    if(commit==null) throw new InvalidOperationException("Windows returned no preference-save operation.");
                    commit.Completed += delegate(IPrintSchemaTicket result,int commitStatus) { onUi(delegate {
                        try
                        {
                            if(commitStatus<0) throw new InvalidOperationException("Windows could not save the laser settings.");
                            // Request completion must occur on the UI thread.
                            saved();
                        }
                        catch(Exception error) {PrinterExtensionProgram.Log(new InvalidOperationException("Completing native preference save.",error));failed(error.Message);}
                    }); };
                    commit.Start();
                }
                catch(Exception error) {PrinterExtensionProgram.Log(new InvalidOperationException("Validating/committing native preferences.",error));failed(error.Message);}
            }); };
            validation.Start();
        }

        public void Complete()
        { if(!ended) { context.Request.Complete(); ended=true; } }

        public void Cancel()
        {
            // Microsoft's extension sample reports operator cancellation with
            // S_FALSE. A failure HRESULT asks Windows to display its fallback UI.
            if(!ended) { context.Request.Cancel(1,"Printer properties cancelled."); ended=true; }
        }
    }

    public static class PrinterExtensionProgram
    {
        public static readonly Guid DriverId=new Guid("72F09BB3-5810-4A7E-9960-69E4151CDF30");
        static readonly Guid PreferencesReason=new Guid("EC8F261F-267C-469F-B5D6-3933023C29CC");
        static PrinterExtensionManager manager;

        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if(args.Length==3 && args[0]=="--preview")
                {
                    Application.EnableVisualStyles();
                    Application.SetCompatibleTextRenderingDefault(false);
                    using(PrinterPreferencesForm preview=new PrinterPreferencesForm(
                        new PreviewPreferencesSession(PreferenceData.Read(args[1],args[2]))))
                    { preview.Text+=" (Preview)"; Application.Run(preview); }
                    return 0;
                }
                if(args.Length<1 || new Guid(args[0])!=DriverId) return 2;
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                using(Control dispatch=new Control())
                {
                    IntPtr handle=dispatch.Handle;
                    ApplicationContext application=new ApplicationContext();
                    manager=new PrinterExtensionManager();
                    manager.OnDriverEvent += delegate(IPrinterExtensionEventArgs request) {
                        dispatch.BeginInvoke(new Action(delegate {
                            if(request.ReasonId!=PreferencesReason)
                            { request.Request.Cancel(unchecked((int)0x80004001),"Unsupported printer event."); application.ExitThread(); return; }
                            try
                            {
                                NativePreferencesSession session=new NativePreferencesSession(request,
                                    action=>dispatch.BeginInvoke(action));
                                Form form;
                                if(session.SupportsFullSettings)
                                {
                                    ClassicPreferencesForm complete=new ClassicPreferencesForm(session.FullSettings,
                                        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AuroraJobServer","classic-presets"),session.SaveFull);
                                    complete.FormClosed+=delegate {if(complete.Result==null) session.Cancel();};
                                    form=complete;
                                }
                                else form=new PrinterPreferencesForm(session);
                                // Complete the caller's request on the form's UI thread, after CommitAsync.
                                form.FormClosed += delegate {
                                    try { session.Complete(); }
                                    catch(Exception error) { Log(error); }
                                    finally { application.ExitThread(); }
                                };
                                if(request.WindowModal!=0)
                                {
                                    if(request.WindowParent!=IntPtr.Zero) form.ShowDialog(new WindowOwner(request.WindowParent));
                                    else form.ShowDialog();
                                    form.Dispose();
                                }
                                else if(request.WindowParent!=IntPtr.Zero) form.Show(new WindowOwner(request.WindowParent));
                                else form.Show();
                            }
                            catch(Exception error)
                            {
                                Log(error);
                                request.Request.Cancel(unchecked((int)0x80004005),error.Message);
                                application.ExitThread();
                            }
                        }));
                    };
                    manager.EnableEvents(DriverId);
                    Application.Run(application);
                    manager.DisableEvents();
                }
                return 0;
            }
            catch(Exception error) { Log(error); return 1; }
        }

        internal static void Log(Exception error)
        {
            try { File.AppendAllText(Path.Combine(Path.GetTempPath(),"AuroraPrinterProperties.log"),
                    DateTime.UtcNow.ToString("o")+" "+error+Environment.NewLine); }
            catch(IOException) { }
        }

        sealed class WindowOwner : IWin32Window
        {
            readonly IntPtr handle;
            public WindowOwner(IntPtr handle) { this.handle=handle; }
            public IntPtr Handle { get { return handle; } }
        }
    }

    public sealed class PreviewPreferencesSession : IPreferencesSession
    {
        readonly PreferenceData data;
        public PreferenceData Data { get { return data; } }
        public PreviewPreferencesSession(PreferenceData data) { this.data=data; }
        public void Save(Dictionary<string,string> selection,Action saved,Action<string> failed)
        { data.Check(selection); saved(); } // Preview never saves printer defaults or a job.
        public void Cancel() { }
    }
}
