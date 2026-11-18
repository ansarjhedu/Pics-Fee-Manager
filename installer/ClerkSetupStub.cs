using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace PicsFee
{
    internal static class ClerkSetupStub
    {
        private const string MagicText = "PICSCLERKSETUP1";

        [STAThread]
        private static int Main()
        {
            try
            {
                string path = Process.GetCurrentProcess().MainModule.FileName;
                byte[] magic = Encoding.ASCII.GetBytes(MagicText);
                using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                {
                    if (stream.Length < magic.Length + 12)
                        return Fail("This setup file is incomplete. Save it again from the Clerks page on the principal's computer.");
                    stream.Seek(-magic.Length, SeekOrigin.End);
                    byte[] found = ReadExact(stream, magic.Length);
                    for (int i = 0; i < magic.Length; i++)
                    {
                        if (found[i] != magic[i])
                            return Fail("This setup file is incomplete. Save it again from the Clerks page on the principal's computer.");
                    }
                    stream.Seek(-(magic.Length + 4), SeekOrigin.End);
                    int configLength = BitConverter.ToInt32(ReadExact(stream, 4), 0);
                    if (configLength < 2 || configLength > 100000)
                        return Fail("This setup file is incomplete. Save it again from the Clerks page on the principal's computer.");
                    stream.Seek(-(magic.Length + 12), SeekOrigin.End);
                    long setupLength = BitConverter.ToInt64(ReadExact(stream, 8), 0);
                    long configPos = stream.Length - magic.Length - 12 - configLength;
                    long setupPos = configPos - setupLength;
                    if (setupPos < 0 || setupLength < 1000)
                        return Fail("This setup file is incomplete. Save it again from the Clerks page on the principal's computer.");

                    stream.Seek(configPos, SeekOrigin.Begin);
                    string config = Encoding.UTF8.GetString(ReadExact(stream, configLength));
                    string host = Field(config, "host");
                    string fingerprint = Field(config, "fingerprint");
                    string username = Field(config, "username");
                    string port = NumberField(config, "port");
                    if (host.Length == 0 || fingerprint.Length == 0 || port.Length == 0)
                        return Fail("This setup file is incomplete. Save it again from the Clerks page on the principal's computer.");

                    string temp = Path.Combine(Path.GetTempPath(), "PICS-Clerk-Setup");
                    Directory.CreateDirectory(temp);
                    string setupPath = Path.Combine(temp, "PICS Fee Desk Setup.exe");
                    stream.Seek(setupPos, SeekOrigin.Begin);
                    using (FileStream output = new FileStream(setupPath, FileMode.Create, FileAccess.Write))
                        CopyExact(stream, output, setupLength);

                    string arguments = "/HOST=" + host + " /PORT=" + port + " /FP=" + fingerprint;
                    if (username.Length > 0)
                        arguments += " /CLERK=" + username;
                    ProcessStartInfo start = new ProcessStartInfo();
                    start.FileName = setupPath;
                    start.Arguments = arguments;
                    start.UseShellExecute = true;
                    start.WorkingDirectory = temp;
                    Process setup = Process.Start(start);
                    if (setup == null)
                        return Fail("The clerk setup could not be started.");
                    setup.WaitForExit();
                    return setup.ExitCode;
                }
            }
            catch (Exception)
            {
                return Fail("This setup file could not be opened. Save it again from the Clerks page on the principal's computer.");
            }
        }

        private static string Field(string json, string name)
        {
            string token = "\"" + name + "\":\"";
            int start = json.IndexOf(token, StringComparison.Ordinal);
            if (start < 0)
                return "";
            start += token.Length;
            int end = json.IndexOf('"', start);
            if (end < 0)
                return "";
            return json.Substring(start, end - start);
        }

        private static string NumberField(string json, string name)
        {
            string token = "\"" + name + "\":";
            int start = json.IndexOf(token, StringComparison.Ordinal);
            if (start < 0)
                return "";
            start += token.Length;
            int end = start;
            while (end < json.Length && json[end] >= '0' && json[end] <= '9')
                end++;
            if (end == start)
                return "";
            return json.Substring(start, end - start);
        }

        private static byte[] ReadExact(Stream stream, int count)
        {
            byte[] buffer = new byte[count];
            int offset = 0;
            while (offset < count)
            {
                int read = stream.Read(buffer, offset, count - offset);
                if (read == 0)
                    throw new EndOfStreamException();
                offset += read;
            }
            return buffer;
        }

        private static void CopyExact(Stream source, Stream dest, long count)
        {
            byte[] buffer = new byte[1024 * 1024];
            long left = count;
            while (left > 0)
            {
                int want = left > buffer.Length ? buffer.Length : (int)left;
                int read = source.Read(buffer, 0, want);
                if (read == 0)
                    throw new EndOfStreamException();
                dest.Write(buffer, 0, read);
                left -= read;
            }
        }

        private static int Fail(string message)
        {
            MessageBox.Show(message, "PICS Fee Desk", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 1;
        }
    }
}
