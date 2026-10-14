package dev.launchpad;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;

@Configuration
public class SecurityConfig {
    @Bean
    SecurityFilterChain security(HttpSecurity http,
        @Value("${launchpad.developer-token}") String developer,
        @Value("${launchpad.other-token}") String other,
        @Value("${launchpad.operator-token}") String operator) throws Exception {
        if (List.of(developer, other, operator).stream().anyMatch(t -> t.length() < 24)
            || developer.equals(other) || developer.equals(operator) || other.equals(operator)) {
            throw new IllegalArgumentException("Configure three distinct tokens of at least 24 characters");
        }
        var tokens = List.of(new Token(developer, "vishal", "DEVELOPER"),
            new Token(other, "other-team", "DEVELOPER"), new Token(operator, "platform-ops", "OPERATOR"));
        return http
            // Only explicitly supplied bearer credentials; no cookies, sessions or Basic auth.
            .csrf(c -> c.disable())
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(a -> a
                .requestMatchers("/", "/index.html", "/app.js", "/style.css", "/actuator/health", "/api-docs.yaml").permitAll()
                .requestMatchers("/api/deployments/*/approve", "/actuator/prometheus").hasRole("OPERATOR")
                .requestMatchers(HttpMethod.GET, "/api/**").authenticated()
                .requestMatchers("/api/**").authenticated()
                .anyRequest().denyAll())
            .exceptionHandling(e -> e
                .authenticationEntryPoint((req, res, ex) -> error(res, 401, "Authentication required"))
                .accessDeniedHandler((req, res, ex) -> error(res, 403, "Access denied")))
            .addFilterBefore(new OncePerRequestFilter() {
                @Override protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
                    throws ServletException, IOException {
                    String header = req.getHeader("Authorization");
                    if (header != null && header.startsWith("Bearer ")) {
                        byte[] provided = header.substring(7).getBytes(StandardCharsets.UTF_8);
                        for (Token t : tokens) {
                            if (MessageDigest.isEqual(provided, t.value().getBytes(StandardCharsets.UTF_8))) {
                                SecurityContextHolder.getContext().setAuthentication(
                                    new UsernamePasswordAuthenticationToken(t.name(), null,
                                        List.of(new SimpleGrantedAuthority("ROLE_" + t.role()))));
                            }
                        }
                    }
                    chain.doFilter(req, res);
                }
            }, UsernamePasswordAuthenticationFilter.class).build();
    }
    private record Token(String value, String name, String role) {}
    private static void error(HttpServletResponse res, int status, String detail) throws IOException {
        res.setStatus(status); res.setContentType("application/problem+json");
        res.getWriter().write("{\"status\":" + status + ",\"detail\":\"" + detail + "\"}");
    }
}
