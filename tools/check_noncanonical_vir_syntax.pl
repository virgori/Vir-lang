#!/usr/bin/env perl
use strict;
use warnings;
use File::Find qw(find);
use File::Spec;

# VIRC-ISS-0048 repository guard.  This scans Vir source-bearing regions,
# rather than raw text, so examples in comments/strings do not become false
# positives.  Explicit negative fixtures and the embedded GPU foreign source
# are intentionally outside the maintained Vir-source contract.

my @roots = @ARGV ? @ARGV : qw(compiler/src compiler/generated stdlib/vir tests tools examples);
my @files;

sub excluded_path {
    my ($path) = @_;
    $path =~ s{\\}{/}g;
    return 1 if $path =~ m{(?:^|/)stdlib/vir/gpu/kernels\.vri$};
    return 1 if $path =~ m{(?:^|/)tests/strict_v2/noncanonical_[^/]*_rejected\.vri$};
    return 0;
}

for my $root (@roots) {
    next if !-e $root;
    if (-f $root) {
        push @files, $root if $root =~ /\.vri\z/ && !excluded_path($root);
        next;
    }
    find(
        {
            no_chdir => 1,
            wanted => sub {
                return if !-f $_ || $_ !~ /\.vri\z/;
                push @files, $File::Find::name if !excluded_path($File::Find::name);
            },
        },
        $root,
    );
}

sub source_only {
    my ($text) = @_;
    my $out = '';
    my $state = 'source';
    my $quote = '';
    my $length = length($text);

    for (my $i = 0; $i < $length; $i++) {
        my $ch = substr($text, $i, 1);
        my $three = substr($text, $i, 3);
        my $two = substr($text, $i, 2);

        if ($state eq 'line-comment') {
            if ($ch eq "\n") {
                $state = 'source';
                $out .= "\n";
            } else {
                $out .= ' ';
            }
            next;
        }
        if ($state eq 'star-comment') {
            if ($three eq '#*#') {
                $out .= '   ';
                $i += 2;
                $state = 'source';
            } else {
                $out .= $ch eq "\n" ? "\n" : ' ';
            }
            next;
        }
        if ($state eq 'hash-comment') {
            if ($two eq '##') {
                $out .= '  ';
                $i += 1;
                $state = 'source';
            } else {
                $out .= $ch eq "\n" ? "\n" : ' ';
            }
            next;
        }
        if ($state eq 'string') {
            if ($ch eq "\\") {
                $out .= ' ';
                if ($i + 1 < $length) {
                    my $escaped = substr($text, $i + 1, 1);
                    $out .= $escaped eq "\n" ? "\n" : ' ';
                    $i += 1;
                }
            } elsif ($ch eq $quote) {
                $out .= ' ';
                $state = 'source';
            } else {
                $out .= $ch eq "\n" ? "\n" : ' ';
            }
            next;
        }

        if ($three eq '#*#') {
            $out .= '   ';
            $i += 2;
            $state = 'star-comment';
        } elsif ($two eq '##') {
            my $line_end = index($text, "\n", $i + 2);
            $line_end = $length if $line_end < 0;
            my $rest = substr($text, $i + 2, $line_end - ($i + 2));
            $out .= '  ';
            $i += 1;
            # Repository doc comments commonly use `## text` as a line form;
            # a delimiter-only `##` retains the legacy block-comment meaning.
            $state = $rest =~ /^\s*\z/ ? 'hash-comment' : 'line-comment';
        } elsif ($ch eq '#') {
            $out .= ' ';
            $state = 'line-comment';
        } elsif ($ch eq '"' || $ch eq "'") {
            $quote = $ch;
            $out .= ' ';
            $state = 'string';
        } else {
            $out .= $ch;
        }
    }
    return $out;
}

my @violations;
for my $path (sort @files) {
    open my $handle, '<:raw', $path or die "cannot read $path: $!\n";
    local $/;
    my $raw = <$handle>;
    close $handle;
    my $source = source_only($raw);
    my @lines = split /\n/, $source, -1;

    for my $line_index (0 .. $#lines) {
        my $line = $lines[$line_index];
        my @checks = (
            [qr/\breturn\b/, "keyword 'return' (use 'out')"],
            [qr/\bwhile\b/, "keyword 'while' (use 'when ... loop')"],
            [qr/&&/, "operator '&&' (use '&')"],
            [qr/<<=/, "operator '<<=' (use 'x = x shl value')"],
            [qr/>>=/, "operator '>>=' (use 'x = x shr value')"],
            [qr/<<(?!=)/, "operator '<<' (use 'shl')"],
            [qr/(?<!\|)\|(?![|=])/, "single '|' (use 'or')"],
            [qr/(?<![A-Za-z0-9_\)\]\:])~/, "prefix '~' (use 'bnot(expr)')"],
        );
        for my $check (@checks) {
            my ($pattern, $label) = @$check;
            while ($line =~ /$pattern/g) {
                push @violations, sprintf('%s:%d:%d: %s', $path, $line_index + 1, $-[0] + 1, $label);
            }
        }
    }
}

if (@violations) {
    print STDERR "noncanonical Vir source spellings found:\n";
    print STDERR "$_\n" for @violations;
    exit 1;
}

print 'PASS: maintained Vir sources use canonical VIRC-ISS-0048 spellings (' . scalar(@files) . " files)\n";
exit 0;
