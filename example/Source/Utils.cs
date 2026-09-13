// The Clear BSD License
//
// Copyright (c) 2026 Ian Hylton
// All rights reserved.


namespace CmdRouter.Example.Source;


public static class Utils {
    /// <summary> Prints to this stdout with a prefix of <c> > </c>. </summary>
    public static void Print(params string?[] m) => Console.WriteLine(value:$"> {string.Join(separator:" ", m)}");

    /// <summary> Prints to this stdout with a prefix of <c> ! </c>. </summary>
    public static void Error(params string?[] m) => Console.WriteLine(value:$"! {string.Join(separator:" ", m)}");

    /// <summary>
    ///     Traverses upward from the executing assembly directory until a directory
    ///     containing <c> uv.lock </c> is found.
    ///     This equivalent to our Python implementation of <c> Paths._get_root </c>.
    /// </summary>
    public static string ThisPath() {
        var start = Path.GetDirectoryName(typeof(Utils).Assembly.Location) ?? AppContext.BaseDirectory;
        var current = new DirectoryInfo(start);

        while (true) {
            if (File.Exists(Path.Combine(current.FullName, "uv.lock")))
                return current.FullName;

            if (current.Parent is null)
                return Directory.GetCurrentDirectory();

            current = current.Parent;
        }
    }
}
